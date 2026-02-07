Invocations
===========

When you call a routine, it returns an `Invocation`
that can be submitted or awaited.

```python
from basic import yielding

# Submit directly
yielding(7).submit()

# Or await from an async routine
await yielding(7)
```

Priority
--------

Invocations have a priority from 0 (lowest) to 9 (highest),
defaulting to 4.
Set priority using the `priority()` context manager:

```python
from queueio import priority

with priority(7):
    yielding(7).submit()
    await yielding(7)
```

Priority propagates to descendent invocations.
