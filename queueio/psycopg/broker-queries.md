# Broker Queries

Scratchpad for working out the SQL needed to implement the Broker interface.

We're Python 3.14 exclusive, so we'll use psycopg's t-string support
for queries. T-strings let us embed parameters directly in the SQL
with safe interpolation, avoiding positional placeholders:

```python
cursor.execute(t"INSERT INTO queueio_tasks (queue, body, priority) VALUES ({queue}, {body}, {priority})")

# For identifiers (table/column names), use :i
cursor.execute(t"NOTIFY {channel:i}, {payload:l}")
```

See: https://www.psycopg.org/psycopg3/docs/basic/tstrings.html

## Schema

Before any queries, we need tables. Open questions marked with (?).

```sql
CREATE TABLE queueio_queues (
    name TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE queueio_tasks (
    id BIGSERIAL PRIMARY KEY,       -- or UUID (?)
    queue TEXT NOT NULL REFERENCES queueio_queues(name),
    body BYTEA NOT NULL,
    priority INTEGER NOT NULL DEFAULT 4,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, processing
    worker_id TEXT,                  -- identifies the claiming worker
    heartbeat TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_claimable
    ON queueio_tasks (queue, priority, created_at)
    WHERE status = 'pending';
```

Open questions:
- Should completed tasks be deleted or moved to a separate table?
- Is BIGSERIAL sufficient or do we need UUIDs for distributed ID generation?
- Should `status` be an enum or just text?
- Do we need a `worker` registration table, or is `worker_id` on the task
  sufficient for heartbeat-based reaping?


## `enqueue(body, *, queue, priority)`

Insert a task into the queue.

```python
cursor.execute(t"INSERT INTO queueio_tasks (queue, body, priority) VALUES ({queue}, {body}, {priority})")
```

Might also want to `NOTIFY` here to wake up consumers:

```python
cursor.execute(t"INSERT INTO queueio_tasks (queue, body, priority) VALUES ({queue}, {body}, {priority})")
cursor.execute(t"NOTIFY queueio, {queue:l}")
```

Open question: Can we combine the INSERT and NOTIFY in a single round trip?
psycopg can pipeline or use `execute` with multiple statements, but NOTIFY
isn't part of the INSERT. Might need two statements in one transaction.


## `sync(queues, *, recreate)`

Ensure queues exist. With `recreate=True`, destroy and recreate all
resources, losing any pending messages.

```python
for queue in queues:
    if recreate:
        cursor.execute(t"DELETE FROM queueio_tasks WHERE queue = {queue}")
        cursor.execute(t"DELETE FROM queueio_queues WHERE name = {queue}")
    cursor.execute(
        t"INSERT INTO queueio_queues (name) VALUES ({queue}) ON CONFLICT (name) DO NOTHING"
    )
```

With `ON DELETE CASCADE` on the foreign key, the recreate path simplifies:

```python
for queue in queues:
    if recreate:
        cursor.execute(t"DELETE FROM queueio_queues WHERE name = {queue}")
    cursor.execute(
        t"INSERT INTO queueio_queues (name) VALUES ({queue}) ON CONFLICT (name) DO NOTHING"
    )
```


## `purge(*, queue)`

Remove all tasks from a queue without deleting the queue itself.

```python
cursor.execute(t"DELETE FROM queueio_tasks WHERE queue = {queue}")
```


## `receive(queuespec) -> Receiver`

No query here — this creates a Receiver instance. The Receiver handles
the actual claiming. See receiver-queries.md.


## `shutdown()`

No query — application-level cleanup (close connections, stop threads).


## Portability Notes

- `INSERT ... ON CONFLICT DO NOTHING` — PostgreSQL-specific.
  MySQL uses `INSERT IGNORE`, others vary.
- `NOTIFY` — PostgreSQL-specific. Other databases would need polling.
- `BYTEA` — PostgreSQL. MySQL uses `BLOB`, others vary.
- `TIMESTAMPTZ` — PostgreSQL. MySQL uses `TIMESTAMP`, others vary.
- `BIGSERIAL` — PostgreSQL. MySQL uses `BIGINT AUTO_INCREMENT`.

These are mostly type/syntax differences, not fundamental. An ORM would
abstract them. Raw SQL would need per-database variants.
