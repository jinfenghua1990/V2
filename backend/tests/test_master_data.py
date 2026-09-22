from app.master_data import resolve_party, resolve_product
from app.models import ExternalBinding, Party, PartyRole, Product, SourceRecord


def party_input(**overrides):
    value = {
        "kind": "organization",
        "name": "浙江示例公司",
        "role": "customer",
        "tax_identifier": "91330000DEMO00001",
        "source_system": "jky",
        "source_object_type": "customer",
        "source_external_id": "C-001",
        "payload": {"name": "浙江示例公司"},
    }
    value.update(overrides)
    return value


def product_input(**overrides):
    value = {
        "name": "示例产品",
        "product_code": "P-001",
        "barcode": "690000000001",
        "source_system": "jky",
        "source_object_type": "product",
        "source_external_id": "G-001",
        "payload": {"name": "示例产品"},
    }
    value.update(overrides)
    return value


def test_same_party_from_multiple_sources_uses_one_identity(db_session):
    first = resolve_party(db_session, **party_input())
    second = resolve_party(
        db_session,
        **party_input(
            role="supplier",
            source_system="1688",
            source_object_type="seller",
            source_external_id="S-77",
            payload={"seller": "浙江示例公司"},
        ),
    )

    assert first["status"] == "created"
    assert second["status"] == "matched"
    assert first["entity_id"] == second["entity_id"]
    assert db_session.query(Party).count() == 1
    assert db_session.query(ExternalBinding).count() == 2
    assert db_session.query(SourceRecord).count() == 2
    assert db_session.query(PartyRole).count() == 2


def test_same_name_without_strong_identifier_waits_for_review(db_session):
    first = resolve_party(
        db_session,
        **party_input(tax_identifier="", source_external_id="C-002"),
    )
    second = resolve_party(
        db_session,
        **party_input(
            tax_identifier="",
            source_system="manual",
            source_object_type="customer",
            source_external_id="manual-1",
        ),
    )

    assert first["status"] == "created"
    assert second["status"] == "needs_review"
    assert second["entity_id"] is None
    assert second["candidate_ids"] == [first["entity_id"]]
    assert db_session.query(Party).count() == 1
    assert db_session.query(ExternalBinding).count() == 1
    assert db_session.query(SourceRecord).count() == 2


def test_same_product_from_multiple_sources_uses_one_product(db_session):
    first = resolve_product(db_session, **product_input())
    second = resolve_product(
        db_session,
        **product_input(
            name="示例产品（销售名称）",
            source_system="1688",
            source_object_type="goods",
            source_external_id="A-001",
            payload={"title": "示例产品（销售名称）"},
        ),
    )

    assert first["status"] == "created"
    assert second["status"] == "matched"
    assert first["entity_id"] == second["entity_id"]
    assert db_session.query(Product).count() == 1
    assert db_session.query(ExternalBinding).count() == 2


def test_same_product_name_without_strong_identifier_waits_for_review(db_session):
    first = resolve_product(
        db_session,
        **product_input(product_code="", barcode="", source_external_id="G-002"),
    )
    second = resolve_product(
        db_session,
        **product_input(
            product_code="",
            barcode="",
            source_system="manual",
            source_object_type="product",
            source_external_id="manual-product-1",
        ),
    )

    assert first["status"] == "created"
    assert second["status"] == "needs_review"
    assert db_session.query(Product).count() == 1
    assert db_session.query(ExternalBinding).count() == 1


def test_duplicate_source_import_keeps_both_source_records(db_session):
    first = resolve_party(db_session, **party_input())
    second = resolve_party(db_session, **party_input())

    assert first["entity_id"] == second["entity_id"]
    assert second["status"] == "matched"
    assert db_session.query(Party).count() == 1
    assert db_session.query(SourceRecord).count() == 2
    assert db_session.query(ExternalBinding).count() == 1
