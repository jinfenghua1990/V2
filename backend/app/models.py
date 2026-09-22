from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.utcnow()


class Party(Base):
    """唯一主体身份；customer/supplier/company 都通过角色表达。"""

    __tablename__ = "parties"
    __table_args__ = (
        Index("ix_parties_normalized_name", "normalized_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    merged_into_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("parties.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class PartyRole(Base):
    """角色不是身份；同一主体可以同时拥有多个角色。"""

    __tablename__ = "party_roles"
    __table_args__ = (
        UniqueConstraint("party_id", "role", name="uq_party_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    party_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class PartyIdentifier(Base):
    """主体的强识别信息，例如税号或统一社会信用代码。"""

    __tablename__ = "party_identifiers"
    __table_args__ = (
        UniqueConstraint("kind", "normalized_value", name="uq_party_identifier"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    party_id: Mapped[str] = mapped_column(
        ForeignKey("parties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(256), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")


class Product(Base):
    """唯一产品主档；业务模块不能另建采购/销售/库存商品表。"""

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_normalized_name", "normalized_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class ProductIdentifier(Base):
    """产品内部编码、条码等强识别信息。"""

    __tablename__ = "product_identifiers"
    __table_args__ = (
        UniqueConstraint("kind", "normalized_value", name="uq_product_identifier"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(256), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")


class SourceRecord(Base):
    """不可覆盖的来源证据；重复接收也保留新记录。"""

    __tablename__ = "source_records"
    __table_args__ = (
        Index("ix_source_records_lookup", "source_system", "source_object_type", "source_external_id"),
        Index("ix_source_records_content_hash", "content_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    source_object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unresolved")
    resolved_entity_type: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    resolved_entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    candidate_entity_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class ExternalBinding(Base):
    """一个来源编号只能指向一个规范实体。"""

    __tablename__ = "external_bindings"
    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_object_type",
            "source_external_id",
            name="uq_external_binding_source_key",
        ),
        Index("ix_external_bindings_entity", "entity_type", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    source_object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_external_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("source_records.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class AuditEvent(Base):
    """不可覆盖的主数据处理事件；身份认证接入前先保留系统处理轨迹。"""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_source_record", "source_record_id"),
        Index("ix_audit_events_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("source_records.id", ondelete="SET NULL"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(24), nullable=False, default="system")
    actor_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
