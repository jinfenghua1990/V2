"""create canonical master data tables

Revision ID: 0001_canonical_master_data
Revises:
Create Date: 2026-09-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_canonical_master_data"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parties",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("canonical_name", sa.String(length=256), nullable=False),
        sa.Column("normalized_name", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("merged_into_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["merged_into_id"], ["parties.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parties_normalized_name", "parties", ["normalized_name"])

    op.create_table(
        "party_roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("party_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("party_id", "role", name="uq_party_role"),
    )
    op.create_index("ix_party_roles_party_id", "party_roles", ["party_id"])

    op.create_table(
        "party_identifiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("party_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=256), nullable=False),
        sa.Column("normalized_value", sa.String(length=256), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "normalized_value", name="uq_party_identifier"),
    )
    op.create_index("ix_party_identifiers_party_id", "party_identifiers", ["party_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_code", sa.String(length=128), nullable=False),
        sa.Column("canonical_name", sa.String(length=512), nullable=False),
        sa.Column("normalized_name", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_code"),
    )
    op.create_index("ix_products_normalized_name", "products", ["normalized_name"])

    op.create_table(
        "product_identifiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=256), nullable=False),
        sa.Column("normalized_value", sa.String(length=256), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "normalized_value", name="uq_product_identifier"),
    )
    op.create_index("ix_product_identifiers_product_id", "product_identifiers", ["product_id"])

    op.create_table(
        "source_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("source_object_type", sa.String(length=64), nullable=False),
        sa.Column("source_external_id", sa.String(length=256), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("resolution_status", sa.String(length=24), nullable=False),
        sa.Column("resolved_entity_type", sa.String(length=24), nullable=True),
        sa.Column("resolved_entity_id", sa.String(length=36), nullable=True),
        sa.Column("candidate_entity_ids", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_records_lookup",
        "source_records",
        ["source_system", "source_object_type", "source_external_id"],
    )
    op.create_index("ix_source_records_content_hash", "source_records", ["content_hash"])

    op.create_table(
        "external_bindings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("source_object_type", sa.String(length=64), nullable=False),
        sa.Column("source_external_id", sa.String(length=256), nullable=False),
        sa.Column("source_record_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(["source_record_id"], ["source_records.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_system",
            "source_object_type",
            "source_external_id",
            name="uq_external_binding_source_key",
        ),
    )
    op.create_index("ix_external_bindings_entity", "external_bindings", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_external_bindings_entity", table_name="external_bindings")
    op.drop_table("external_bindings")
    op.drop_index("ix_source_records_content_hash", table_name="source_records")
    op.drop_index("ix_source_records_lookup", table_name="source_records")
    op.drop_table("source_records")
    op.drop_index("ix_product_identifiers_product_id", table_name="product_identifiers")
    op.drop_table("product_identifiers")
    op.drop_index("ix_products_normalized_name", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_party_identifiers_party_id", table_name="party_identifiers")
    op.drop_table("party_identifiers")
    op.drop_index("ix_party_roles_party_id", table_name="party_roles")
    op.drop_table("party_roles")
    op.drop_index("ix_parties_normalized_name", table_name="parties")
    op.drop_table("parties")
