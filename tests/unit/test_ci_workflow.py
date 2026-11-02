"""CI must never run tests that need a network or an API key."""
from pathlib import Path

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "tests.yml"


def test_the_workflow_deselects_both_integration_and_llm_tests():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'python -m pytest -m "not integration and not llm"' in text


def test_the_workflow_gives_the_job_no_secrets():
    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8")
