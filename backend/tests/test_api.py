def test_healthz(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "service": "v2",
        "dataModel": "canonical-master-v1",
    }


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
    assert review_queue.json()[0]["payload"] == {"raw_name": "查询主体"}
