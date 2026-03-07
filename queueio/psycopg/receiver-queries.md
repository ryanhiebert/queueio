# Receiver Queries

Scratchpad for working out the SQL needed to implement the Receiver interface.

The Receiver is the most complex piece — it handles claiming tasks, managing
capacity (prefetch), pause/unpause for suspended tasks, finishing (ack),
and heartbeat-based liveness.


## Claim (called during iteration)

Atomically claim a task: lock it, update status, return it. Single round trip.

```sql
WITH claimed AS (
    SELECT id FROM queueio_tasks
    WHERE queue IN (:queues)
      AND status = 'pending'
    ORDER BY priority, created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE queueio_tasks
SET status = 'processing',
    worker_id = :worker_id,
    heartbeat = now()
FROM claimed
WHERE queueio_tasks.id = claimed.id
RETURNING queueio_tasks.*;
```

Open questions:
- How do we respect `queuespec.concurrency`? The Pika implementation uses
  prefetch (QoS). Here we'd need to track how many tasks this worker currently
  owns (active + paused) and only claim when under the limit. This is
  application-level tracking, not a query concern.
- Should we claim from multiple queues in round-robin order, or let the
  database pick based on priority? The QueueSpec says "roughly round-robin."
  Could alternate the queue order in successive claims.
- What about NOTIFY-based wakeup vs polling? The claim query works either
  way, but the iteration loop needs to either poll on a timer or LISTEN
  and wake up on NOTIFY.


## Claim with stale task recovery

Same as above, but also reclaims tasks from dead workers.

```sql
WITH claimed AS (
    SELECT id FROM queueio_tasks
    WHERE (
        queue IN (:queues)
        AND status = 'pending'
    ) OR (
        queue IN (:queues)
        AND status = 'processing'
        AND heartbeat < now() - :timeout * INTERVAL '1 second'
    )
    ORDER BY priority, created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE queueio_tasks
SET status = 'processing',
    worker_id = :worker_id,
    heartbeat = now()
FROM claimed
WHERE queueio_tasks.id = claimed.id
RETURNING queueio_tasks.*;
```

Open question: Should stale tasks be prioritized over pending tasks, or
mixed in by priority/created_at? Prioritizing stale tasks ensures faster
recovery but could starve new work if there's a flood of stale tasks.

Portability: The `INTERVAL` syntax varies. PostgreSQL uses
`INTERVAL '1 second'`, MySQL uses `INTERVAL 1 SECOND`.


## `pause(message)`

No query needed. This is purely application-level capacity tracking.
The Pika implementation adjusts prefetch_count. Here we'd decrement a
local counter that controls whether the claim loop asks for more work.

The task stays in `processing` status — it's still owned by this worker.
The heartbeat must continue covering it.


## `unpause(message)`

No query needed. Increment the local capacity counter, allowing the claim
loop to fetch more work.


## `finish(message)`

The task is done. Delete it (or mark it complete).

```sql
DELETE FROM queueio_tasks WHERE id = :task_id;
```

Or if we want to keep history:

```sql
UPDATE queueio_tasks
SET status = 'complete',
    completed_at = now()
WHERE id = :task_id;
```

Open question: Delete vs soft-delete. The Journal/event store already
captures the lifecycle. Keeping completed tasks in the queue table adds
VACUUM pressure for no clear benefit. Deleting is probably right.


## Heartbeat (background thread)

Periodically update the heartbeat for all tasks owned by this worker.

```sql
UPDATE queueio_tasks
SET heartbeat = now()
WHERE worker_id = :worker_id
  AND status = 'processing';
```

This runs on a timer (e.g., every 30 seconds) in a background thread.
Single query covers all active and paused tasks for this worker.

Alternative: Use a separate `workers` table with a single heartbeat row
per worker, and join on it for stale detection. Fewer UPDATE rows, but
adds a join to the claim query.

```sql
-- Worker heartbeat (single row)
UPDATE queueio_workers
SET heartbeat = now()
WHERE id = :worker_id;
```

```sql
-- Stale detection via join
WITH claimed AS (
    SELECT t.id FROM queueio_tasks t
    LEFT JOIN queueio_workers w ON t.worker_id = w.id
    WHERE (
        t.queue IN (:queues)
        AND t.status = 'pending'
    ) OR (
        t.queue IN (:queues)
        AND t.status = 'processing'
        AND w.heartbeat < now() - :timeout * INTERVAL '1 second'
    )
    ORDER BY t.priority, t.created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE queueio_tasks
SET status = 'processing',
    worker_id = :worker_id,
    heartbeat = now()
FROM claimed
WHERE queueio_tasks.id = claimed.id
RETURNING queueio_tasks.*;
```

Open question: Per-task heartbeat vs per-worker heartbeat table. Per-worker
is fewer writes but adds schema complexity. Per-task is simpler schema but
more write volume under high concurrency with many paused tasks.


## Iteration / Blocking

The `__iter__` method needs to block waiting for work. Two approaches:

### Polling

```python
while not shutdown:
    if at_capacity():
        sleep(poll_interval)
        continue
    row = execute(claim_query)
    if row:
        yield Message(row.body)
    else:
        sleep(poll_interval)
```

### LISTEN/NOTIFY

```sql
LISTEN queueio;
```

```python
while not shutdown:
    if at_capacity():
        # Still need to wait, but LISTEN will wake us
        wait_for_notify(timeout=poll_interval)
        continue
    row = execute(claim_query)
    if row:
        yield Message(body=row.body)
    else:
        wait_for_notify(timeout=poll_interval)
```

LISTEN/NOTIFY requires a persistent connection that stays in LISTEN mode.
This could be the same dedicated connection used for claims and heartbeats,
since LISTEN persists across transactions.

Portability: LISTEN/NOTIFY is PostgreSQL-specific. Other databases would
fall back to polling.


## `shutdown()`

Stop the iteration loop, clean up owned tasks.

```sql
-- Return all owned tasks to pending (graceful shutdown)
UPDATE queueio_tasks
SET status = 'pending',
    worker_id = NULL,
    heartbeat = NULL
WHERE worker_id = :worker_id
  AND status = 'processing';
```

Open question: On graceful shutdown, should we return tasks to pending
immediately, or let them drain (finish processing active ones, return
only paused/suspended ones)?


## Portability Notes

- `WITH ... FOR UPDATE SKIP LOCKED` in a CTE — PostgreSQL-specific.
  MySQL supports `FOR UPDATE SKIP LOCKED` but not inside a CTE used
  with UPDATE ... FROM. Would need a different query structure.
- `UPDATE ... FROM` — PostgreSQL extension. MySQL uses `UPDATE ... JOIN`.
- `RETURNING` — PostgreSQL-specific. MySQL has no equivalent (would need
  a separate SELECT after UPDATE).
- `LISTEN/NOTIFY` — PostgreSQL-specific.
- `INTERVAL` syntax varies across databases.

The CTE + UPDATE FROM + RETURNING pattern that makes the claim a single
round trip is **heavily PostgreSQL-specific**. On MySQL, you'd need at
minimum two round trips (SELECT FOR UPDATE SKIP LOCKED, then UPDATE).
This is the strongest signal that the single-round-trip claim may not
be portable.
