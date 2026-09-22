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
