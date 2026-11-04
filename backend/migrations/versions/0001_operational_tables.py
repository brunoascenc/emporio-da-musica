"""Create the six operational tables from the supplied CSV headers."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_operational_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "categories",
        sa.Column("category_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
    )
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("phone", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("city", sa.Text, nullable=False),
    )
    op.create_table(
        "products",
        sa.Column("product_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("price_brl", sa.Numeric(12, 2), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.category_id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("stock_quantity", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("specs", JSONB, nullable=False),
        sa.Column("created_at", sa.Date, nullable=False),
        sa.CheckConstraint("price_brl >= 0", name="products_price_nonnegative"),
        sa.CheckConstraint("stock_quantity >= 0", name="products_stock_nonnegative"),
        sa.CheckConstraint("status IN ('active', 'coming_soon', 'discontinued')", name="products_status_valid"),
        sa.CheckConstraint("jsonb_typeof(specs) = 'object'", name="products_specs_object"),
    )
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_table(
        "orders",
        sa.Column("order_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("customers.customer_id"), nullable=False),
        sa.Column("order_date", sa.Date, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("total_brl", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.Text, nullable=False),
        sa.Column("tracking_code", sa.Text, nullable=True),
        sa.Column("estimated_delivery", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.CheckConstraint("total_brl >= 0", name="orders_total_nonnegative"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')", name="orders_status_valid"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_table(
        "order_items",
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.order_id"), primary_key=True, autoincrement=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.product_id"), primary_key=True, autoincrement=False),
        sa.CheckConstraint("quantity > 0", name="order_items_quantity_positive"),
    )
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])
    op.create_table(
        "promotions",
        sa.Column("promotion_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.product_id"), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.CheckConstraint("discount_percent BETWEEN 0 AND 100", name="promotions_discount_valid"),
    )
    op.create_index("ix_promotions_product_id", "promotions", ["product_id"])


def downgrade():
    for table in ("promotions", "order_items", "orders", "products", "customers", "categories"):
        op.drop_table(table)
