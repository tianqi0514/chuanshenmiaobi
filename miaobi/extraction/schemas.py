from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SampleProfileProposal(StrictModel):
    document_type: str
    audience: str | None = None
    tone: str
    outline: list[str] = Field(default_factory=list)
    section_responsibilities: list[str] = Field(default_factory=list)
    formatting_notes: list[str] = Field(default_factory=list)


class EntityProposal(StrictModel):
    name: str
    entity_type: str
    aliases: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    needs_confirmation: bool = True


class ClaimProposal(StrictModel):
    subject: str
    predicate: str
    object_text: str
    claim_type: Literal["fact_statement", "requirement", "forecast", "recommendation", "opinion"]
    evidence_ids: list[str] = Field(min_length=1)
    needs_confirmation: bool = True


class FactProposal(StrictModel):
    claim_id: str
    subject: str
    predicate: str
    object_value: str
    value_type: Literal["text", "number", "date", "boolean", "reference"] = "text"
    unit: str | None = None
    time_scope: str | None = None
    applicable_scope: str | None = None
    evidence_ids: list[str] = Field(min_length=1)
    needs_confirmation: bool = True


class RelationProposal(StrictModel):
    subject_entity_id: str
    predicate: str
    object_entity_id: str
    fact_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    needs_confirmation: bool = True


class MetricProposal(StrictModel):
    name: str
    metric_type: Literal["atomic", "derived"]
    value: str | int | float | None = None
    unit: str | None = None
    formula: str | None = None
    dependency_names: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    target_section_hints: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True


class SampleProfileEnvelope(StrictModel):
    items: list[SampleProfileProposal] = Field(default_factory=list, max_length=1)


class EntityEnvelope(StrictModel):
    items: list[EntityProposal] = Field(default_factory=list, max_length=100)


class ClaimEnvelope(StrictModel):
    items: list[ClaimProposal] = Field(default_factory=list, max_length=150)


class FactEnvelope(StrictModel):
    items: list[FactProposal] = Field(default_factory=list, max_length=150)


class RelationEnvelope(StrictModel):
    items: list[RelationProposal] = Field(default_factory=list, max_length=150)


class MetricEnvelope(StrictModel):
    items: list[MetricProposal] = Field(default_factory=list, max_length=100)
