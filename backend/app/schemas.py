from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PartyResolveRequest(BaseModel):
    kind: Literal["person", "organization"]
    name: str = Field(min_length=1, max_length=256)
    role: Optional[str] = Field(default=None, min_length=1, max_length=32)
    tax_identifier: str = Field(default="", max_length=256)
    source_system: str = Field(min_length=1, max_length=64)
    source_object_type: str = Field(min_length=1, max_length=64)
    source_external_id: str = Field(min_length=1, max_length=256)
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "source_system", "source_object_type", "source_external_id")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("名称和来源标识不能只包含空白字符")
        return value

    @field_validator("role")
    @classmethod
    def reject_blank_role(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("主体角色不能为空")
        return value.strip() if value is not None else None


class ProductResolveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    product_code: str = Field(default="", max_length=128)
    barcode: str = Field(default="", max_length=128)
    source_system: str = Field(min_length=1, max_length=64)
    source_object_type: str = Field(min_length=1, max_length=64)
    source_external_id: str = Field(min_length=1, max_length=256)
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "source_system", "source_object_type", "source_external_id")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("名称和来源标识不能只包含空白字符")
        return value


class SourceRecordResolveRequest(BaseModel):
    entity_type: Literal["party", "product"]
    entity_id: str = Field(min_length=1, max_length=36)
    party_role: Optional[str] = Field(default=None, min_length=1, max_length=32)


class IdentifierResponse(BaseModel):
    kind: str
    value: str


class PartyResponse(BaseModel):
    id: str
    kind: Literal["person", "organization"]
    canonical_name: str
    status: str
    merged_into_id: Optional[str]
    roles: List[str]
    identifiers: List[IdentifierResponse]


class ProductResponse(BaseModel):
    id: str
    product_code: str
    canonical_name: str
    status: str
    identifiers: List[IdentifierResponse]


class SourceRecordReviewResponse(BaseModel):
    id: str
    source_system: str
    source_object_type: str
    source_external_id: str
    resolution_status: Literal["needs_review"]
    candidate_ids: List[str]
    payload: Dict[str, Any]
    received_at: datetime


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    entity_type: str
    entity_id: Optional[str]
    source_record_id: Optional[str]
    actor_type: str
    actor_id: Optional[str]
    details: Dict[str, Any]
    created_at: datetime


class ResolveResponse(BaseModel):
    status: Literal["created", "matched", "needs_review"]
    entity_type: Literal["party", "product"]
    entity_id: Optional[str]
    source_record_id: str
    candidate_ids: List[str] = Field(default_factory=list)
    message: str
