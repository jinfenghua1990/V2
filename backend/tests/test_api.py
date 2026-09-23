from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.main import create_app


def test_healthz(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "v2",
        "dataModel": "canonical-master-v1",
        "database": "ok",
    }


def test_healthz_reports_missing_schema():
    engine = create_engine("sqlite://")
    client = TestClient(
        create_app(
            session_factory=sessionmaker(bind=engine),
            enforce_auth=False,
        )
    )

    response = client.get("/healthz")

    assert response.status_code == 503
    assert response.json()["detail"] == "数据库或主数据结构不可用"


def test_app_factory_does_not_create_database_schema():
    engine = create_engine("sqlite://")

    create_app(
        session_factory=sessionmaker(bind=engine),
        enforce_auth=False,
    )

    assert inspect(engine).get_table_names() == []


def test_api_resolves_same_party_to_one_identity(client):
    payload = {
        "kind": "organization",
        "name": "API 示例公司",
        "role": "customer",
        "tax_identifier": "91330000API000001",
        "source_system": "manual",
        "source_object_type": "customer",
        "source_external_id": "api-1",
        "payload": {"name": "API 示例公司"},
    }

    first = client.post("/api/v1/parties/resolve", json=payload)
    second = client.post(
        "/api/v1/parties/resolve",
        json={**payload, "source_system": "1688", "source_external_id": "api-2"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "created"
    assert second.json()["status"] == "matched"
    assert first.json()["entity_id"] == second.json()["entity_id"]


def test_api_allows_explicit_review_resolution(client):
    first = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "待审核公司",
            "role": "customer",
            "tax_identifier": "REVIEW-001",
            "source_system": "manual",
            "source_object_type": "customer",
            "source_external_id": "review-1",
        },
    )
    review = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "待审核公司",
            "role": "supplier",
            "source_system": "1688",
            "source_object_type": "supplier",
            "source_external_id": "review-2",
        },
    )

    assert first.status_code == 200
    assert review.status_code == 200
    assert review.json()["status"] == "needs_review"

    resolved = client.post(
        f"/api/v1/source-records/{review.json()['source_record_id']}/resolve",
        json={
            "entity_type": "party",
            "entity_id": first.json()["entity_id"],
            "party_role": "supplier",
        },
    )

    assert resolved.status_code == 200
    assert resolved.json()["status"] == "matched"
    assert resolved.json()["entity_id"] == first.json()["entity_id"]

    retry = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "待审核公司",
            "role": "supplier",
            "source_system": "1688",
            "source_object_type": "supplier",
            "source_external_id": "review-2",
        },
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "matched"
    assert retry.json()["entity_id"] == first.json()["entity_id"]


def test_api_rejects_unknown_review_target(client):
    response = client.post(
        "/api/v1/source-records/not-found/resolve",
        json={"entity_type": "party", "entity_id": "missing"},
    )

    assert response.status_code == 404


def test_api_reads_canonical_records_and_review_queue(client):
    party = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "查询主体",
            "role": "customer",
            "tax_identifier": "READ-001",
            "source_system": "manual",
            "source_object_type": "customer",
            "source_external_id": "read-party-1",
        },
    )
    product = client.post(
        "/api/v1/products/resolve",
        json={
            "name": "查询产品",
            "product_code": "READ-P-001",
            "source_system": "manual",
            "source_object_type": "product",
            "source_external_id": "read-product-1",
        },
    )
    review = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "查询主体",
            "source_system": "1688",
            "source_object_type": "supplier",
            "source_external_id": "read-review-1",
            "payload": {"raw_name": "查询主体"},
        },
    )

    party_read = client.get(f"/api/v1/parties/{party.json()['entity_id']}")
    product_read = client.get(f"/api/v1/products/{product.json()['entity_id']}")
    review_queue = client.get("/api/v1/source-records/review")

    assert party_read.status_code == 200
    assert party_read.json()["canonical_name"] == "查询主体"
    assert party_read.json()["roles"] == ["customer"]
    assert party_read.json()["identifiers"] == [
        {"kind": "tax_identifier", "value": "READ-001"}
    ]
    assert product_read.status_code == 200
    assert product_read.json()["product_code"] == "READ-P-001"
    assert product_read.json()["identifiers"] == [
        {"kind": "product_code", "value": "READ-P-001"}
    ]
    assert review.status_code == 200
    assert review.json()["status"] == "needs_review"
    assert review_queue.status_code == 200
    assert review_queue.json()[0]["id"] == review.json()["source_record_id"]
    assert review_queue.json()[0]["payload"] == {
        "request_fields": {
            "kind": "organization",
            "name": "查询主体",
            "role": None,
            "tax_identifier": "",
            "source_system": "1688",
            "source_object_type": "supplier",
            "source_external_id": "read-review-1",
        },
        "payload": {"raw_name": "查询主体"},
    }

    audit = client.get(
        f"/api/v1/audit-events?entity_type=party&entity_id={party.json()['entity_id']}"
    )
    assert audit.status_code == 200
    assert {item["event_type"] for item in audit.json()} >= {
        "party.created",
        "source_record.matched",
    }


def test_api_requires_bearer_key_and_records_api_actor(secure_client, monkeypatch):
    payload = {
        "kind": "organization",
        "name": "受保护主体",
        "role": "customer",
        "tax_identifier": "AUTH-001",
        "source_system": "manual",
        "source_object_type": "customer",
        "source_external_id": "auth-1",
    }

    assert secure_client.get("/api/v1/source-records/review").status_code == 401
    assert secure_client.post("/api/v1/parties/resolve", json=payload).status_code == 401
    assert secure_client.post(
        "/api/v1/parties/resolve",
        json=payload,
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 403

    headers = {"Authorization": "Bearer test-api-key"}
    created = secure_client.post(
        "/api/v1/parties/resolve",
        json=payload,
        headers=headers,
    )
    assert created.status_code == 200

    audit = secure_client.get(
        f"/api/v1/audit-events?entity_id={created.json()['entity_id']}",
        headers=headers,
    )
    assert audit.status_code == 200
    assert audit.json()[0]["actor_type"] == "api"
    assert audit.json()[0]["actor_id"] == "test-operator"

    monkeypatch.setenv("V2_API_ROLE", "viewer")
    assert secure_client.post(
        "/api/v1/parties/resolve",
        json={**payload, "source_external_id": "auth-2"},
        headers=headers,
    ).status_code == 403


def test_api_rejects_blank_names_and_source_keys(client):
    party = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "   ",
            "source_system": "manual",
            "source_object_type": "customer",
            "source_external_id": "blank-party",
        },
    )
    product = client.post(
        "/api/v1/products/resolve",
        json={
            "name": "正常产品",
            "source_system": "manual",
            "source_object_type": "product",
            "source_external_id": "   ",
        },
    )

    assert party.status_code == 422
    assert product.status_code == 422


def test_api_sends_cross_entity_source_conflicts_to_review(client):
    product = client.post(
        "/api/v1/products/resolve",
        json={
            "name": "冲突产品",
            "product_code": "CONFLICT-P-1",
            "source_system": "manual",
            "source_object_type": "record",
            "source_external_id": "conflict-1",
        },
    )
    party_conflict = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "冲突主体",
            "source_system": "manual",
            "source_object_type": "record",
            "source_external_id": "conflict-1",
        },
    )
    party = client.post(
        "/api/v1/parties/resolve",
        json={
            "kind": "organization",
            "name": "另一个冲突主体",
            "source_system": "manual",
            "source_object_type": "record",
            "source_external_id": "conflict-2",
        },
    )
    product_conflict = client.post(
        "/api/v1/products/resolve",
        json={
            "name": "另一个冲突产品",
            "source_system": "manual",
            "source_object_type": "record",
            "source_external_id": "conflict-2",
        },
    )

    assert product.status_code == 200
    assert party_conflict.status_code == 200
    assert party_conflict.json()["status"] == "needs_review"
    assert party_conflict.json()["entity_id"] is None
    assert party.status_code == 200
    assert product_conflict.status_code == 200
    assert product_conflict.json()["status"] == "needs_review"
    assert product_conflict.json()["entity_id"] is None
    review_ids = {
        record["id"]
        for record in client.get("/api/v1/source-records/review").json()
    }
    assert party_conflict.json()["source_record_id"] in review_ids
    assert product_conflict.json()["source_record_id"] in review_ids
    for response in (party_conflict, product_conflict):
        events = client.get(
            f"/api/v1/audit-events?source_record_id={response.json()['source_record_id']}"
        )
        assert events.status_code == 200
        assert "external_binding.type_conflict" in {
            event["event_type"] for event in events.json()
        }
