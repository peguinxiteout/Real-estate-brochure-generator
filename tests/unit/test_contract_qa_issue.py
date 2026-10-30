import pytest
from pydantic import ValidationError

from brochure.contracts.qa import QAIssue


def issue_data(**overrides):
    data = {
        "check": "text_overflow",
        "page": 2,
        "severity": "error",
        "note": "overview_intro is 640 chars, budget is 600",
        "route_to": "copywriter",
    }
    data.update(overrides)
    return data


def test_valid_qa_issue_parses():
    issue = QAIssue.model_validate(issue_data())
    assert (issue.check, issue.page, issue.severity, issue.route_to) == ("text_overflow", 2, "error", "copywriter")


def test_page_is_optional_for_whole_brochure_issues():
    assert QAIssue.model_validate(issue_data(page=None)).page is None


@pytest.mark.parametrize("field,value", [("severity", "fatal"), ("route_to", "vision"), ("page", 0)])
def test_invalid_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        QAIssue.model_validate(issue_data(**{field: value}))


def test_route_to_is_required_so_every_issue_says_who_fixes_it():
    data = issue_data()
    del data["route_to"]
    with pytest.raises(ValidationError, match="route_to"):
        QAIssue.model_validate(data)
