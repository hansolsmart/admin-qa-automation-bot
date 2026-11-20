from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Scenario = Literal["TC-N-01", "TC-N-02", "TC-N-03", "TC-EX-01", "TC-EX-02", "TC-EX-03"]
SCENARIOS = {
    "TC-N-01": ("관리자 로그인", "qa/test_normal.py::test_login"),
    "TC-N-02": ("항목 등록", "qa/test_normal.py::test_create_item"),
    "TC-N-03": ("항목 수정", "qa/test_normal.py::test_update_item"),
    "TC-EX-01": ("등록 응답 단절", "qa/test_network.py::test_committed_registration_after_response_loss"),
    "TC-EX-02": ("특수문자 입력", "qa/test_special.py::test_special_characters_round_trip"),
    "TC-EX-03": ("중복 제출", "qa/test_duplicate.py::test_rapid_click_and_concurrent_requests"),
}
VERDICTS = ("PASS", "FAIL", "ERROR", "SKIPPED")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LoginInput(Input):
    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Annotated[str, Field(min_length=1, max_length=256)]

    @field_validator("username", "password")
    @classmethod
    def validate_encoding(cls, value):
        value.encode("utf-8")
        return value


class ItemFields(Input):
    @field_validator("name", "description", check_fields=False)
    @classmethod
    def literal_text(cls, value, info):
        if value is None or "\x00" in value or (info.field_name == "name" and not value.strip()):
            raise ValueError("Invalid text")
        value.encode("utf-8")
        return value


class ItemInput(ItemFields):
    name: Annotated[str, Field(min_length=1, max_length=100)]
    description: Annotated[str, Field(max_length=500)] = ""


class ItemPatch(ItemFields):
    name: Annotated[str | None, Field(min_length=1, max_length=100)] = None
    description: Annotated[str | None, Field(max_length=500)] = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one item field is required")
        return self


class QARunInput(Input):
    scenarios: Annotated[list[Scenario], Field(min_length=1, max_length=6)]

    @field_validator("scenarios")
    @classmethod
    def distinct_scenarios(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Scenario IDs must be distinct")
        return values
