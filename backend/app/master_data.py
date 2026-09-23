from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from .models import (
    ExternalBinding,
    AuditEvent,
    Party,
    PartyIdentifier,
    PartyRole,
    Product,
    ProductIdentifier,
    SourceRecord,
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").strip().casefold()
    return re.sub(r"\s+", " ", normalized)


def normalize_identifier(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").strip().casefold()
    return re.sub(r"[\s\-_/]", "", normalized)


def _content_hash(
    source_system: str,
    object_type: str,
    external_id: str,
    payload: Dict[str, Any],
) -> str:
    raw = json.dumps(
        {
            "source_system": source_system,
            "object_type": object_type,
            "external_id": external_id,
            "payload": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _new_source_record(
    db: Session,
    *,
    source_system: str,
    source_object_type: str,
    source_external_id: str,
    payload: Dict[str, Any],
    actor_type: str = "system",
    actor_id: Optional[str] = None,
) -> SourceRecord:
    record = SourceRecord(
        source_system=source_system,
        source_object_type=source_object_type,
        source_external_id=source_external_id,
        content_hash=_content_hash(
            source_system, source_object_type, source_external_id, payload
        ),
        payload=payload,
    )
    db.add(record)
    db.flush()
    _audit_event(
        db,
        event_type="source_record.received",
        entity_type="source_record",
        entity_id=record.id,
        source_record_id=record.id,
        details={"content_hash": record.content_hash},
        actor_type=actor_type,
        actor_id=actor_id,
    )
    return record


def _audit_event(
    db: Session,
    *,
    event_type: str,
    entity_type: str,
    entity_id: Optional[str],
    source_record_id: Optional[str],
    details: Dict[str, Any],
    actor_type: str = "system",
    actor_id: Optional[str] = None,
) -> None:
    db.add(
        AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            source_record_id=source_record_id,
            actor_type=actor_type,
            actor_id=actor_id,
            details=details,
        )
    )


def _record_resolution(
    db: Session,
    source: SourceRecord,
    *,
    entity_type: str,
    entity_id: Optional[str],
    status: str,
    reason: str,
    candidates: Optional[List[str]] = None,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
) -> None:
    candidate_ids = candidates or []
    _mark_source(
        source,
        entity_type=entity_type,
        entity_id=entity_id,
        status=status,
        candidates=candidate_ids,
    )
    _audit_event(
        db,
        event_type=f"source_record.{status}",
        entity_type=entity_type,
        entity_id=entity_id,
        source_record_id=source.id,
        details={"reason": reason, "candidate_ids": candidate_ids},
        actor_type=actor_type,
        actor_id=actor_id,
    )


def _mark_source(
    source: SourceRecord,
    *,
    entity_type: str,
    entity_id: Optional[str],
    status: str,
    candidates: Optional[List[str]] = None,
) -> None:
    source.resolution_status = status
    source.resolved_entity_type = entity_type if entity_id else None
    source.resolved_entity_id = entity_id
    source.candidate_entity_ids = candidates or []


def _ensure_party_role(db: Session, party_id: str, role: Optional[str]) -> None:
    if not role:
        return
    existing = (
        db.query(PartyRole)
        .filter(PartyRole.party_id == party_id, PartyRole.role == role)
        .one_or_none()
    )
    if existing is None:
        db.add(PartyRole(party_id=party_id, role=role))


def _bind(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    source: SourceRecord,
) -> None:
    db.add(
        ExternalBinding(
            entity_type=entity_type,
            entity_id=entity_id,
            source_system=source.source_system,
            source_object_type=source.source_object_type,
            source_external_id=source.source_external_id,
            source_record_id=source.id,
        )
    )


def resolve_party(
    db: Session,
    *,
    kind: str,
    name: str,
    role: Optional[str],
    tax_identifier: str,
    source_system: str,
    source_object_type: str,
    source_external_id: str,
    payload: Dict[str, Any],
    actor_type: str = "system",
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    request_fields = {
        "kind": kind,
        "name": name,
        "role": role,
        "tax_identifier": tax_identifier,
        "source_system": source_system,
        "source_object_type": source_object_type,
        "source_external_id": source_external_id,
    }
    if not normalize_text(name):
        raise ValueError("主体名称不能为空")
    if not all(value.strip() for value in (source_system, source_object_type, source_external_id)):
        raise ValueError("来源系统、对象类型和外部编号不能为空")
    if role is not None and not role.strip():
        raise ValueError("主体角色不能为空")
    source_system = source_system.strip()
    source_object_type = source_object_type.strip()
    source_external_id = source_external_id.strip()
    role = role.strip() if role is not None else None
    source_payload = {"request_fields": request_fields, "payload": payload}

    source = _new_source_record(
        db,
        source_system=source_system,
        source_object_type=source_object_type,
        source_external_id=source_external_id,
        payload=source_payload,
        actor_type=actor_type,
        actor_id=actor_id,
    )

    binding = (
        db.query(ExternalBinding)
        .filter(
            ExternalBinding.source_system == source_system,
            ExternalBinding.source_object_type == source_object_type,
            ExternalBinding.source_external_id == source_external_id,
        )
        .one_or_none()
    )
    if binding is not None:
        if binding.entity_type != "party":
            _record_resolution(
                db,
                source,
                entity_type="party",
                entity_id=None,
                status="needs_review",
                reason="binding_entity_type_conflict",
                actor_type=actor_type,
                actor_id=actor_id,
            )
            _audit_event(
                db,
                event_type="external_binding.type_conflict",
                entity_type=binding.entity_type,
                entity_id=binding.entity_id,
                source_record_id=source.id,
                details={"requested_entity_type": "party", "binding_id": binding.id},
                actor_type=actor_type,
                actor_id=actor_id,
            )
            db.commit()
            return _result(
                "needs_review",
                "party",
                None,
                source.id,
                [],
                "该来源编号已绑定到产品，已加入待审核队列",
            )
        party = db.get(Party, binding.entity_id)
        if party is None:
            raise ValueError("外部映射指向不存在的主体")
        _ensure_party_role(db, party.id, role)
        _record_resolution(
            db,
            source,
            entity_type="party",
            entity_id=party.id,
            status="matched",
            reason="external_binding",
            actor_type=actor_type,
            actor_id=actor_id,
        )
        db.commit()
        return _result("matched", "party", party.id, source.id, [], "已按外部来源映射到同一主体")

    normalized_identifier = normalize_identifier(tax_identifier)
    if normalized_identifier:
        identifier = (
            db.query(PartyIdentifier)
            .filter(
                PartyIdentifier.kind == "tax_identifier",
                PartyIdentifier.normalized_value == normalized_identifier,
            )
            .one_or_none()
        )
        if identifier is not None:
            _ensure_party_role(db, identifier.party_id, role)
            _bind(db, entity_type="party", entity_id=identifier.party_id, source=source)
            _record_resolution(
                db,
                source,
                entity_type="party",
                entity_id=identifier.party_id,
                status="matched",
                reason="strong_identifier",
                actor_type=actor_type,
                actor_id=actor_id,
            )
            db.commit()
            return _result("matched", "party", identifier.party_id, source.id, [], "已按强身份标识映射到同一主体")

    normalized_name = normalize_text(name)
    candidates = [
        row[0]
        for row in db.query(Party.id)
        .filter(Party.normalized_name == normalized_name, Party.status == "active")
        .all()
    ]
    if candidates:
        _record_resolution(
            db,
            source,
            entity_type="party",
            entity_id=None,
            status="needs_review",
            reason="name_only",
            candidates=candidates,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        db.commit()
        return _result("needs_review", "party", None, source.id, candidates, "名称相同但缺少足够身份依据，等待人工确认")

    party = Party(kind=kind, canonical_name=name.strip(), normalized_name=normalized_name)
    db.add(party)
    db.flush()
    _audit_event(
        db,
        event_type="party.created",
        entity_type="party",
        entity_id=party.id,
        source_record_id=source.id,
        details={"kind": party.kind, "canonical_name": party.canonical_name},
        actor_type=actor_type,
        actor_id=actor_id,
    )
    if normalized_identifier:
        db.add(
            PartyIdentifier(
                party_id=party.id,
                kind="tax_identifier",
                value=tax_identifier.strip(),
                normalized_value=normalized_identifier,
                source_system=source_system,
            )
        )
    _ensure_party_role(db, party.id, role)
    _bind(db, entity_type="party", entity_id=party.id, source=source)
    _record_resolution(
        db,
        source,
        entity_type="party",
        entity_id=party.id,
        status="matched",
        reason="created",
        actor_type=actor_type,
        actor_id=actor_id,
    )
    db.commit()
    return _result("created", "party", party.id, source.id, [], "已创建唯一规范主体")


def resolve_product(
    db: Session,
    *,
    name: str,
    product_code: str,
    barcode: str,
    source_system: str,
    source_object_type: str,
    source_external_id: str,
    payload: Dict[str, Any],
    actor_type: str = "system",
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    request_fields = {
        "name": name,
        "product_code": product_code,
        "barcode": barcode,
        "source_system": source_system,
        "source_object_type": source_object_type,
        "source_external_id": source_external_id,
    }
    if not normalize_text(name):
        raise ValueError("产品名称不能为空")
    if not all(value.strip() for value in (source_system, source_object_type, source_external_id)):
        raise ValueError("来源系统、对象类型和外部编号不能为空")
    source_system = source_system.strip()
    source_object_type = source_object_type.strip()
    source_external_id = source_external_id.strip()
    source_payload = {"request_fields": request_fields, "payload": payload}

    source = _new_source_record(
        db,
        source_system=source_system,
        source_object_type=source_object_type,
        source_external_id=source_external_id,
        payload=source_payload,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    binding = (
        db.query(ExternalBinding)
        .filter(
            ExternalBinding.source_system == source_system,
            ExternalBinding.source_object_type == source_object_type,
            ExternalBinding.source_external_id == source_external_id,
        )
        .one_or_none()
    )
    if binding is not None:
        if binding.entity_type != "product":
            _record_resolution(
                db,
                source,
                entity_type="product",
                entity_id=None,
                status="needs_review",
                reason="binding_entity_type_conflict",
                actor_type=actor_type,
                actor_id=actor_id,
            )
            _audit_event(
                db,
                event_type="external_binding.type_conflict",
                entity_type=binding.entity_type,
                entity_id=binding.entity_id,
                source_record_id=source.id,
                details={"requested_entity_type": "product", "binding_id": binding.id},
                actor_type=actor_type,
                actor_id=actor_id,
            )
            db.commit()
            return _result(
                "needs_review",
                "product",
                None,
                source.id,
                [],
                "该来源编号已绑定到主体，已加入待审核队列",
            )
        product = db.get(Product, binding.entity_id)
        if product is None:
            raise ValueError("外部映射指向不存在的产品")
        _record_resolution(
            db,
            source,
            entity_type="product",
            entity_id=product.id,
            status="matched",
            reason="external_binding",
            actor_type=actor_type,
            actor_id=actor_id,
        )
        db.commit()
        return _result("matched", "product", product.id, source.id, [], "已按外部来源映射到同一产品")

    identifiers = []
    for kind, value in (("product_code", product_code), ("barcode", barcode)):
        normalized = normalize_identifier(value)
        if normalized:
            identifiers.append((kind, value.strip(), normalized))
    for kind, _value, normalized in identifiers:
        candidate = (
            db.query(ProductIdentifier)
            .filter(ProductIdentifier.kind == kind, ProductIdentifier.normalized_value == normalized)
            .one_or_none()
        )
        if candidate is not None:
            _bind(db, entity_type="product", entity_id=candidate.product_id, source=source)
            _record_resolution(
                db,
                source,
                entity_type="product",
                entity_id=candidate.product_id,
                status="matched",
                reason="strong_identifier",
                actor_type=actor_type,
                actor_id=actor_id,
            )
            db.commit()
            return _result("matched", "product", candidate.product_id, source.id, [], "已按产品强标识映射到同一产品")

    normalized_name = normalize_text(name)
    candidates = [
        row[0]
        for row in db.query(Product.id)
        .filter(Product.normalized_name == normalized_name, Product.status == "active")
        .all()
    ]
    if candidates:
        _record_resolution(
            db,
            source,
            entity_type="product",
            entity_id=None,
            status="needs_review",
            reason="name_only",
            candidates=candidates,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        db.commit()
        return _result("needs_review", "product", None, source.id, candidates, "产品名称相同但缺少强标识，等待人工确认")

    code = product_code.strip() or "V2-" + uuid4().hex[:12].upper()
    product = Product(
        product_code=code,
        canonical_name=name.strip(),
        normalized_name=normalized_name,
    )
    db.add(product)
    db.flush()
    _audit_event(
        db,
        event_type="product.created",
        entity_type="product",
        entity_id=product.id,
        source_record_id=source.id,
        details={"product_code": product.product_code, "canonical_name": product.canonical_name},
        actor_type=actor_type,
        actor_id=actor_id,
    )
    if not any(kind == "product_code" for kind, _value, _normalized in identifiers):
        identifiers.append(("product_code", code, normalize_identifier(code)))
    for kind, value, normalized in identifiers:
        db.add(
            ProductIdentifier(
                product_id=product.id,
                kind=kind,
                value=value,
                normalized_value=normalized,
                source_system=source_system,
            )
        )
    _bind(db, entity_type="product", entity_id=product.id, source=source)
    _record_resolution(
        db,
        source,
        entity_type="product",
        entity_id=product.id,
        status="matched",
        reason="created",
        actor_type=actor_type,
        actor_id=actor_id,
    )
    db.commit()
    return _result("created", "product", product.id, source.id, [], "已创建唯一规范产品")


def resolve_source_record(
    db: Session,
    *,
    source_record_id: str,
    entity_type: str,
    entity_id: str,
    party_role: Optional[str] = None,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    source = db.get(SourceRecord, source_record_id)
    if source is None:
        raise LookupError("来源记录不存在")
    if source.resolution_status not in {"unresolved", "needs_review"}:
        raise ValueError("来源记录已经处理，不能重复确认")
    if entity_type == "party":
        entity = db.get(Party, entity_id)
    elif entity_type == "product":
        entity = db.get(Product, entity_id)
    else:
        raise ValueError("不支持的规范实体类型")
    if entity is None:
        raise LookupError("规范实体不存在")
    if entity_type != "party" and party_role:
        raise ValueError("只有主体来源记录可以追加主体角色")

    binding = (
        db.query(ExternalBinding)
        .filter(
            ExternalBinding.source_system == source.source_system,
            ExternalBinding.source_object_type == source.source_object_type,
            ExternalBinding.source_external_id == source.source_external_id,
        )
        .one_or_none()
    )
    if binding is not None:
        if binding.entity_type != entity_type or binding.entity_id != entity_id:
            raise ValueError("外部来源已经绑定到其他规范实体")
    else:
        db.add(
            ExternalBinding(
                entity_type=entity_type,
                entity_id=entity_id,
                source_system=source.source_system,
                source_object_type=source.source_object_type,
                source_external_id=source.source_external_id,
                source_record_id=source.id,
            )
        )
    if entity_type == "party":
        _ensure_party_role(db, entity_id, party_role)
    _record_resolution(
        db,
        source,
        entity_type=entity_type,
        entity_id=entity_id,
        status="matched",
        reason="manual_review",
        actor_type=actor_type,
        actor_id=actor_id,
    )
    _audit_event(
        db,
        event_type="source_record.manually_resolved",
        entity_type=entity_type,
        entity_id=entity_id,
        source_record_id=source.id,
        details={"party_role": party_role},
        actor_type=actor_type,
        actor_id=actor_id,
    )
    db.commit()
    return _result("matched", entity_type, entity_id, source.id, [], "已人工确认并绑定到规范实体")


def get_party(db: Session, party_id: str) -> Dict[str, Any]:
    party = db.get(Party, party_id)
    if party is None:
        raise LookupError("规范主体不存在")
    roles = [
        row[0]
        for row in db.query(PartyRole.role)
        .filter(PartyRole.party_id == party.id)
        .order_by(PartyRole.role)
        .all()
    ]
    identifiers = [
        {"kind": row.kind, "value": row.value}
        for row in db.query(PartyIdentifier)
        .filter(PartyIdentifier.party_id == party.id)
        .order_by(PartyIdentifier.kind, PartyIdentifier.value)
        .all()
    ]
    return {
        "id": party.id,
        "kind": party.kind,
        "canonical_name": party.canonical_name,
        "status": party.status,
        "merged_into_id": party.merged_into_id,
        "roles": roles,
        "identifiers": identifiers,
    }


def get_product(db: Session, product_id: str) -> Dict[str, Any]:
    product = db.get(Product, product_id)
    if product is None:
        raise LookupError("规范产品不存在")
    identifiers = [
        {"kind": row.kind, "value": row.value}
        for row in db.query(ProductIdentifier)
        .filter(ProductIdentifier.product_id == product.id)
        .order_by(ProductIdentifier.kind, ProductIdentifier.value)
        .all()
    ]
    return {
        "id": product.id,
        "product_code": product.product_code,
        "canonical_name": product.canonical_name,
        "status": product.status,
        "identifiers": identifiers,
    }


def list_review_source_records(db: Session, *, limit: int = 100) -> List[Dict[str, Any]]:
    records = (
        db.query(SourceRecord)
        .filter(SourceRecord.resolution_status == "needs_review")
        .order_by(SourceRecord.received_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": record.id,
            "source_system": record.source_system,
            "source_object_type": record.source_object_type,
            "source_external_id": record.source_external_id,
            "resolution_status": record.resolution_status,
            "candidate_ids": record.candidate_entity_ids or [],
            "payload": record.payload,
            "received_at": record.received_at,
        }
        for record in records
    ]


def list_audit_events(
    db: Session,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    source_record_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    query = db.query(AuditEvent)
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditEvent.entity_id == entity_id)
    if source_record_id:
        query = query.filter(AuditEvent.source_record_id == source_record_id)
    events = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit).all()
    return [
        {
            "id": event.id,
            "event_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "source_record_id": event.source_record_id,
            "actor_type": event.actor_type,
            "actor_id": event.actor_id,
            "details": event.details,
            "created_at": event.created_at,
        }
        for event in events
    ]


def _result(
    status: str,
    entity_type: str,
    entity_id: Optional[str],
    source_record_id: str,
    candidate_ids: List[str],
    message: str,
) -> Dict[str, Any]:
    return {
        "status": status,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "source_record_id": source_record_id,
        "candidate_ids": candidate_ids,
        "message": message,
    }
