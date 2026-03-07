# PostgreSQL Broker (`psycopg`)

A Broker and Journal implementation backed by PostgreSQL, using `psycopg` directly
(not through an ORM). Designed for small-scale deployments where running RabbitMQ
is unnecessary overhead.

## How It Works

### Broker (Queue)

Tasks are stored in a PostgreSQL table. Workers claim tasks using
`SELECT FOR UPDATE SKIP LOCKED` inside a CTE that atomically locks, updates,
and returns claimed rows in a single round trip:

```sql
WITH claimed AS (
    SELECT id FROM tasks
    WHERE status = 'pending'
    ORDER BY priority, created_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE tasks
SET status = 'processing',
    worker_id = :worker_id,
    heartbeat = now()
FROM claimed
WHERE tasks.id = claimed.id
RETURNING tasks.*;
```

The transaction is committed immediately after claiming. The task is not held
open in a long-running transaction.

### Journal (Event Store)

Events are appended to a table. Subscribers each track their own position
in the log. `LISTEN/NOTIFY` provides real-time notification of new events
without polling.

### Shared Connection

When a single PostgreSQL URI is configured, the Broker and Journal share
a connection, similar to how the Pika backend shares a single AMQP connection
with separate channels.

## Known Limitations

### No Connection-Based Ownership

This is the most significant difference from RabbitMQ.

With RabbitMQ, task ownership is tied to the AMQP connection. If a worker
crashes, the connection drops, and the broker automatically returns the
message to the queue. No configuration, no edge cases.

The PostgreSQL broker cannot do this. Once a task is claimed and the
transaction commits, ownership is tracked as application state (a `status`
column), not by the database's connection/transaction lifecycle. If a worker
crashes without explicitly finishing or returning the task, the task is
orphaned.

### Heartbeat-Based Recovery

To recover orphaned tasks, each worker periodically updates a heartbeat
timestamp. Tasks owned by workers whose heartbeats have gone stale are
considered abandoned and become available for other workers to claim.

This introduces tradeoffs that do not exist with RabbitMQ:

- **Timeout selection**: You must choose a heartbeat timeout. Too short and
  slow-but-healthy tasks may be stolen. Too long and crashed tasks sit idle
  before recovery.

- **Duplicate processing risk**: If a task legitimately takes longer than the
  timeout, another worker may claim it, leading to the same task running
  concurrently on two workers.

- **Recovery delay**: After a crash, orphaned tasks are not immediately
  available. They remain stuck until the heartbeat timeout expires and another
  worker's claim query picks them up.

With RabbitMQ, none of these are concerns. Recovery is instant, there is no
timeout to tune, and duplicate processing from crash recovery does not happen.

### Suspended Tasks

QueueIO supports suspending a task (releasing worker capacity without
completing the task). With RabbitMQ, suspended tasks are essentially free:
the message stays unacknowledged, the connection stays open, and the broker
knows the consumer is alive via AMQP-level heartbeats.

With PostgreSQL, suspended tasks must continue to be covered by the worker's
heartbeat. A worker with many suspended tasks is not consuming processing
capacity, but its heartbeat must keep running or those tasks will be
incorrectly reclaimed as orphaned.

### Database Requirements

Requires PostgreSQL 9.5+ (`SELECT FOR UPDATE SKIP LOCKED` was introduced
in 9.5).

### PgBouncer Compatibility

If you use PgBouncer in transaction pooling mode (the most common mode),
be aware that the queue infrastructure uses its own persistent `psycopg`
connection, not a pooled connection. The heartbeat and claim queries go
through this dedicated connection, bypassing PgBouncer.

Task code running through an ORM (Django, SQLAlchemy, etc.) can use
PgBouncer normally.

### VACUUM Pressure

High-throughput queue tables generate significant INSERT/UPDATE/DELETE churn,
which increases VACUUM load. At small scale this is negligible. At high
throughput, consider partitioning the queue table or tuning autovacuum
settings.

This does **not** apply to the Journal table, which is append-only.

## When to Use This vs RabbitMQ

**Use PostgreSQL when:**

- You are already running PostgreSQL and do not want another service
- Your worker concurrency is modest (a handful of workers)
- You want a queryable event store (Journal) with zero additional infrastructure
- You are comfortable with heartbeat-based crash recovery

**Use RabbitMQ when:**

- You need connection-based ownership (instant, reliable crash recovery)
- You have many concurrent workers or suspended tasks
- You need the strongest delivery guarantees without timeout tuning
- You are already running RabbitMQ or it is easy to add
