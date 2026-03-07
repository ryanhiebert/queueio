# Journal Queries

Scratchpad for working out the SQL needed to implement the Journal interface.

The Journal is simpler than the Broker — it's broadcast pub/sub, not
competing consumers. No ownership, no locking, no heartbeats.


## Schema

```sql
CREATE TABLE queueio_journal (
    id BIGSERIAL PRIMARY KEY,
    body BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_journal_created
    ON queueio_journal (id);
```

The `id` is the sequence position. Subscribers track their position
by storing the last `id` they've seen.

Open questions:
- Do we need a `channel` or `topic` column for routing, or is one
  global stream sufficient? The Pika implementation uses `amq.topic`
  with routing key `#` (wildcard), so everything goes to all subscribers.
  A single stream may be fine.
- Retention policy: Should old events be pruned? If this is an event
  store, maybe not. If it's just a transport, yes. Could be configurable.
- Partitioning by time for easier cleanup of old events?


## `publish(message)`

Append an event to the journal and notify subscribers.

```sql
INSERT INTO queueio_journal (body)
VALUES (:body);

NOTIFY queueio_journal;
```

Open question: Should the NOTIFY payload include the new `id` so
subscribers can detect gaps? NOTIFY payloads are limited to 8000 bytes,
but an ID is tiny.

```sql
-- With ID in notification
INSERT INTO queueio_journal (body)
VALUES (:body)
RETURNING id;

-- Then notify with the ID
NOTIFY queueio_journal, :id;
```

This requires two statements (INSERT RETURNING, then NOTIFY with the
returned ID), but they can be in the same transaction.


## `subscribe() -> Iterator[bytes]`

Read events from the journal starting from a position, then listen for
new ones.

### Initial catch-up (if resuming from a known position)

```sql
SELECT id, body
FROM queueio_journal
WHERE id > :last_seen_id
ORDER BY id;
```

### Ongoing consumption

```sql
LISTEN queueio_journal;
```

Then on each notification:

```sql
SELECT id, body
FROM queueio_journal
WHERE id > :last_seen_id
ORDER BY id;
```

The pattern:
1. LISTEN on the channel
2. Query for anything after our last known position (catch-up)
3. Wait for NOTIFY
4. On notification, query for new rows since last position
5. Repeat from 3

This handles the race condition where an INSERT + NOTIFY happens between
our initial query and the LISTEN — we always re-query from our last known
position, so we never miss events.

Open question: For the current queueio design, subscribers don't persist
their position — the `PikaJournal` uses an exclusive, auto-delete queue.
Each subscriber starts fresh. So the initial position is "now" (or
`max(id)` at subscribe time), and there's no catch-up. If we want event
store semantics (replay from the beginning), position tracking becomes
important.

```sql
-- Starting fresh: get current position
SELECT COALESCE(MAX(id), 0) AS last_id FROM queueio_journal;
```

### Blocking for new events

```python
while not shutdown:
    # Check for new events since last position
    rows = execute(select_since_query, last_seen_id=position)
    for row in rows:
        position = row.id
        yield row.body

    if not rows:
        # Wait for notification (with timeout as fallback)
        wait_for_notify(timeout=poll_interval)
```

The connection used for LISTEN must be persistent — it can't be returned
to a pool. This is the same constraint as the broker's claim/heartbeat
connection, so they could potentially share the same connection.


## `shutdown()`

Stop listening, close connection.

```sql
UNLISTEN queueio_journal;
```

Application-level: break the iteration loop.


## Portability Notes

- `LISTEN/NOTIFY` — PostgreSQL-specific. This is fundamental to the
  Journal's real-time delivery. Without it, subscribers must poll.
- `BIGSERIAL` — PostgreSQL. MySQL uses `BIGINT AUTO_INCREMENT`.
- `BYTEA` — PostgreSQL. MySQL uses `BLOB`.
- `RETURNING` — PostgreSQL-specific.
- `COALESCE` — Broadly portable.

The Journal is **more portable than the Broker**. The core operations
are just INSERT and SELECT with an auto-increment ID. The only
PostgreSQL-specific feature is LISTEN/NOTIFY for real-time delivery,
and polling is a viable fallback.

If building on Django ORM, the Journal could be a simple model:

```python
class JournalEntry(models.Model):
    body = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'queueio_journal'
```

With LISTEN/NOTIFY added as a PostgreSQL-specific optimization on top.
