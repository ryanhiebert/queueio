# QueueVar

Queue variables propagate context across queue boundaries.
Like Python's `contextvars.ContextVar`,
but values automatically serialize with invocations
and are restored when the worker executes them.

## Defining a QueueVar

```python
from queueio import QueueVar

tenant_id = QueueVar("tenant_id", default=None)
```

Creating a `QueueVar` registers it globally.
All registered queue variables are captured
when an `Invocation` is created,
and restored when the worker runs it.

## Setting and reading values

Set a value with the context manager:

```python
with tenant_id("acme"):
    # tenant_id.get() returns "acme" here
    invocation = my_routine()
    # tenant_id is captured in invocation.context
```

Read the current value with `.get()`:

```python
@routine(name="greet", queue="default")
def greet():
    tid = tenant_id.get()
    print(f"Hello from tenant {tid}")
```

## Propagation

When an invocation is created,
the current values of all registered queue variables are captured
into `invocation.context`.
The worker restores these values before executing the routine,
so any invocations created during execution inherit the parent's context.

```python
@routine(name="inner", queue="work")
def inner():
    return tenant_id.get()

@routine(name="outer", queue="work")
async def outer():
    with tenant_id("acme"):
        result = await inner()
        assert result == "acme"
```

## Accessing context on an invocation

The `QueueVar` instance is a key,
and `QueueContext` behaves like a mapping:

```python
with tenant_id("acme"):
    invocation = my_routine()
    print(invocation.context[tenant_id])  # "acme"
    print(tenant_id in invocation.context)  # True

invocation = my_routine()
# invocation.context[tenant_id] would raise KeyError
print(tenant_id in invocation.context)  # False
print(invocation.context.get(tenant_id, "unknown"))  # "unknown"
```

## Priority

Priority is a built-in queue variable:

```python
from queueio import priority

with priority(2):
    invocation = my_routine()
    print(invocation.context[priority])  # 2
    print(invocation.context.get(priority, priority.default))  # 2
```

## Context variables

Regular `contextvars.ContextVar` values
do not propagate across queue boundaries.
Use `QueueVar` for any context that needs to travel
with invocations.

## Serialization

Values must be JSON-serializable.
The context is included in the serialized invocation
and restored on deserialization.
