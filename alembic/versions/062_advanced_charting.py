"""PRD-62: Advanced Charting.

Revision ID: 062
Revises: 061
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa


revision = "062"
down_revision = "061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # chart_layouts - Saved chart configurations
    op.create_table(
        "chart_layouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Chart settings
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("timeframe", sa.String(10), nullable=True),
        sa.Column("chart_type", sa.String(20), default="candlestick"),
        sa.Column("chart_config", sa.Text(), nullable=True),  # JSON
        # Indicators and drawings stored as JSON
        sa.Column("indicators", sa.Text(), nullable=True),  # JSON array
        sa.Column("drawings", sa.Text(), nullable=True),  # JSON array
        # Grid layout for multi-chart
        sa.Column("grid_layout", sa.Text(), nullable=True),  # JSON
        # Visibility
        sa.Column("is_template", sa.Boolean(), default=False),
        sa.Column("is_public", sa.Boolean(), default=False),
        sa.Column("is_default", sa.Boolean(), default=False),
        # Stats
        sa.Column("view_count", sa.Integer(), default=0),
        sa.Column("copy_count", sa.Integer(), default=0),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chart_layouts_public", "chart_layouts", ["is_public", "is_template"])

    # chart_drawings - Individual drawings on charts
    op.create_table(
        "chart_drawings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("layout_id", sa.String(36), sa.ForeignKey("chart_layouts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("drawing_type", sa.String(30), nullable=False),  # trendline, fib, rectangle, etc.
        # Coordinates and properties
        sa.Column("coordinates", sa.Text(), nullable=False),  # JSON
        sa.Column("style", sa.Text(), nullable=True),  # JSON
        sa.Column("properties", sa.Text(), nullable=True),  # JSON
        # Metadata
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_visible", sa.Boolean(), default=True),
        sa.Column("is_locked", sa.Boolean(), default=False),
        sa.Column("z_index", sa.Integer(), default=0),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )

    # chart_indicator_settings - User indicator preferences
    op.create_table(
        "chart_indicator_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("indicator_name", sa.String(50), nullable=False),
        # Settings
        sa.Column("default_params", sa.Text(), nullable=True),  # JSON
        sa.Column("color_scheme", sa.Text(), nullable=True),  # JSON
        sa.Column("line_style", sa.String(20), default="solid"),
        sa.Column("line_width", sa.Integer(), default=1),
        sa.Column("is_favorite", sa.Boolean(), default=False),
        sa.Column("display_order", sa.Integer(), default=0),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.UniqueConstraint("user_id", "indicator_name", name="uq_chart_indicator_user"),
    )

    # chart_templates - Community chart templates
    op.create_table(
        "chart_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(30), nullable=False, index=True),
        # Template content
        sa.Column("config", sa.Text(), nullable=False),  # JSON
        sa.Column("indicators", sa.Text(), nullable=True),  # JSON
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        # Stats
        sa.Column("usage_count", sa.Integer(), default=0),
        sa.Column("rating", sa.Float(), default=0),
        sa.Column("rating_count", sa.Integer(), default=0),
        # Status
        sa.Column("is_featured", sa.Boolean(), default=False),
        sa.Column("is_approved", sa.Boolean(), default=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("chart_templates")
    op.drop_table("chart_indicator_settings")
    op.drop_table("chart_drawings")
    op.drop_table("chart_layouts")
