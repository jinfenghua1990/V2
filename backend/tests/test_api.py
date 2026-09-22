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
