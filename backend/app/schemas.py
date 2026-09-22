from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PartyResolveRequest(BaseModel):
    kind: Literal["person", "organization"]
    name: str = Field(min_length=1, max_length=256)
    role: Optional[str] = Field(default=None, min_length=1, max_length=32)
    tax_identifier: str = Field(default="", max_length=256)
    source_system: str = Field(min_length=1, max_length=64)
    source_object_type: str = Field(min_length=1, max_length=64)
    source_external_id: str = Field(min_length=1, max_length=256)
    payload: Dict[str, Any] = Field(default_factory=dict)


class ProductResolveRequest(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    product_code: str = Field(default="", max_length=128)
    barcode: str = Field(default="", max_length=128)
    source_system: str = Field(min_length=1, max_length=64)
    source_object_type: str = Field(min_length=1, max_length=64)
    source_external_id: str = Field(min_length=1, max_length=256)
    payload: Dict[str, Any] = Field(default_factory=dict)


class ResolveResponse(BaseModel):
    status: Literal["created", "matched", "needs_review"]
    entity_type: Literal["party", "product"]
    entity_id: Optional[str]
    source_record_id: str
    candidate_ids: List[str] = Field(default_factory=list)
    message: str
