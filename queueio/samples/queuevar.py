from queueio import QueueVar
from queueio import routine

tenant_id = QueueVar[str | None]("tenant_id", default=None)


@routine(name="get_tenant", queue="queuevar")
def get_tenant():
    return tenant_id.get()


@routine(name="demonstrate_queuevar", queue="queuevar")
async def demonstrate_queuevar():
    invocation = get_tenant()
    assert tenant_id not in invocation.context
    assert await invocation is None

    with tenant_id("acme"):
        invocation = get_tenant()
        assert invocation.context[tenant_id] == "acme"
        assert await invocation == "acme"
