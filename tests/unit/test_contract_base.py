import pytest
from pydantic import ValidationError

from brochure.contracts.base import ContractModel


class Sample(ContractModel):
    name: str


def test_unknown_field_is_rejected_so_typos_fail_loudly():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Sample.model_validate({"name": "x", "nmae": "typo"})
