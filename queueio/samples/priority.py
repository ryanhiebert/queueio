from queueio import priority
from queueio import routine


@routine(name="inherited_priority", queue="priority")
def inherited_priority():
    return priority.get()


@routine(name="demonstrate_priority_inheritance", queue="priority")
async def demonstrate_priorities():
    invocation = inherited_priority()
    assert priority not in invocation.context
    assert await invocation == 4

    with priority(2):
        invocation = inherited_priority()
        assert invocation.context[priority] == 2
        assert await invocation == 2
