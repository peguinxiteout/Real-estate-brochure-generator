import pytest


@pytest.mark.parametrize("marker", ["integration", "llm"])
def test_marker_is_registered(pytestconfig, marker):
    registered = [line.split(":")[0].strip() for line in pytestconfig.getini("markers")]
    assert marker in registered
