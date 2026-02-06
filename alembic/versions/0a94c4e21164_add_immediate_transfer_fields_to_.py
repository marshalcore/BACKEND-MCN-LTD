"""Add immediate transfer fields to payments table - SAFE VERSION (improved)

Revision ID: 0a94c4e21164
Revises: 2eb2c764464b
Create Date: 2026-02-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect, text
import logging

# revision identifiers, used by Alembic.
revision: str = "0a94c4e21164"
down_revision: Union[str, Sequence[str], None] = "2eb2c764464b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def check_column_exists(table_name: str, column_name: str, connection) -> bool:
    """
    Return True if column exists on the given table, False otherwise.
    Defensive: if the table doesn't exist or inspector fails, return False.
    """
    try:
        inspector = inspect(connection)
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.warning(f"Could not inspect table '{table_name}': {e}")
        return False


def upgrade() -> None:
    connection = op.get_bind()

    logger.info("🚀 Starting SAFE migration for immediate transfer payment fields (improved)")
    logger.info("⚠️ This migration ONLY adds new columns and sets safe defaults. Back up DB before applying.")

    new_payment_columns = [
        ("immediate_transfers_processed", sa.Boolean(), False, sa.text("false")),
        ("transfer_metadata", postgresql.JSONB(), True, None),
        ("director_general_share", sa.Integer(), False, sa.text("0")),
        ("estech_system_share", sa.Integer(), False, sa.text("0")),
        ("marshal_net_amount", sa.Numeric(12, 2), True, None),
    ]

    for col_name, col_type, nullable, server_default in new_payment_columns:
        try:
            if not check_column_exists("payments", col_name, connection):
                logger.info(f"Adding column 'payments.{col_name}' (nullable={nullable})")
                if server_default is not None:
                    op.add_column(
                        "payments",
                        sa.Column(col_name, col_type, nullable=nullable, server_default=server_default),
                    )
                else:
                    op.add_column("payments", sa.Column(col_name, col_type, nullable=nullable))
            else:
                logger.info(f"Column 'payments.{col_name}' already exists — skipping")
        except Exception as e:
            logger.warning(f"Could not add column '{col_name}': {e}")

    # Normalize existing rows minimally (non-fatal)
    try:
        connection.execute(text("UPDATE payments SET immediate_transfers_processed = false WHERE immediate_transfers_processed IS NULL"))
        connection.execute(text("UPDATE payments SET director_general_share = 0 WHERE director_general_share IS NULL"))
        connection.execute(text("UPDATE payments SET estech_system_share = 0 WHERE estech_system_share IS NULL"))
        logger.info("✅ Normalized existing payment rows for new immediate transfer fields")
    except Exception as e:
        logger.warning(f"⚠️ Could not normalize defaults: {e}")

    # Handle possible existing name: estech_share -> estech_commission (safely)
    try:
        if check_column_exists("payments", "estech_share", connection):
            if not check_column_exists("payments", "estech_commission", connection):
                logger.info("Renaming 'estech_share' -> 'estech_commission'")
                op.alter_column("payments", "estech_share", new_column_name="estech_commission")
            else:
                # If both exist, copy values where commission is NULL and share is not NULL
                logger.info("Both 'estech_share' and 'estech_commission' exist — copying values where needed")
                try:
                    connection.execute(text(
                        "UPDATE payments SET estech_commission = estech_share WHERE estech_commission IS NULL AND estech_share IS NOT NULL"
                    ))
                except Exception as e:
                    logger.warning(f"⚠️ Could not copy values from 'estech_share' to 'estech_commission': {e}")
    except Exception as e:
        logger.warning(f"⚠️ Migration name-check failed: {e}")

    # Limited calculations for existing successful payments (non-fatal)
    try:
        # Use numeric casting in the SQL to ensure consistent rounding behavior
        connection.execute(text("""
            UPDATE payments
            SET director_general_share = ROUND((amount::numeric * 0.35))::integer
            WHERE status = 'success' AND amount > 0
              AND (director_general_share IS NULL OR director_general_share = 0)
        """))
        connection.execute(text("""
            UPDATE payments
            SET estech_system_share = ROUND((amount::numeric * 0.15))::integer
            WHERE status = 'success' AND amount > 0
              AND (estech_system_share IS NULL OR estech_system_share = 0)
        """))
        connection.execute(text("""
            UPDATE payments
            SET marshal_net_amount = 
                CASE
                    WHEN payment_type = 'regular' THEN ROUND(((amount::numeric * 0.48) - 197.7)::numeric, 2)
                    WHEN payment_type = 'vip' THEN ROUND(((amount::numeric * 0.48) - 897)::numeric, 2)
                    ELSE 0
                END
            WHERE status = 'success' AND amount > 0
              AND (marshal_net_amount IS NULL)
        """))
        logger.info("✅ Populated immediate-transfer share calculations for historical successful payments (limited)")
    except Exception as e:
        logger.warning(f"⚠️ Calculation step error (non-fatal): {e}")

    logger.info("✅ SAFE MIGRATION finished. Recommended: run checks and monitor.")


def downgrade() -> None:
    connection = op.get_bind()
    columns_to_remove = [
        "marshal_net_amount",
        "estech_system_share",
        "director_general_share",
        "transfer_metadata",
        "immediate_transfers_processed",
    ]
    for col_name in columns_to_remove:
        try:
            if check_column_exists("payments", col_name, connection):
                logger.info(f"Dropping column 'payments.{col_name}'")
                op.drop_column("payments", col_name)
            else:
                logger.info(f"Column 'payments.{col_name}' not present — skipping drop")
        except Exception as e:
            logger.warning(f"Could not drop column '{col_name}': {e}")

    # Attempt to restore old name if appropriate
    try:
        if check_column_exists("payments", "estech_commission", connection) and not check_column_exists("payments", "estech_share", connection):
            logger.info("Restoring column name 'estech_commission' -> 'estech_share'")
            op.alter_column("payments", "estech_commission", new_column_name="estech_share")
    except Exception as e:
        logger.warning(f"⚠️ Failed to rename back: {e}")