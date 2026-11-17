from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    queries: list[str] = Field(max_length=6)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["guidance", "suspected_bug", "needs_information", "benefit_request", "off_topic"]
    answer: str = Field(min_length=1, max_length=4500)
    source_ids: list[str] = Field(max_length=8)
    title: str = Field(max_length=140)
    expected: str = Field(max_length=1500)
    observed: str = Field(max_length=1500)
    reproduction: list[str] = Field(max_length=10)
    missing_information: list[str] = Field(max_length=3)
