import pytest
import identa
from identa.sdk.registry import AgentRegistry, UnsupportedFrameworkError

class FakeAgent:
    """Object from no recognized framework."""

def test_unknown_framework_raises_clear_error():
    with pytest.raises(UnsupportedFrameworkError) as exc:
        AgentRegistry.detect(FakeAgent())
    assert "Supported frameworks" in str(exc.value)

def test_public_api_does_not_expose_adapters():
    # Adapters must not leak into the top-level namespace
    assert not hasattr(identa, "LangGraphAdapter")
    assert not hasattr(identa, "PydanticAIAdapter")
    assert not hasattr(identa, "BaseAdapter")
