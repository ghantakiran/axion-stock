"""PRD-81: News NLP & Sentiment Analysis.

Revision ID: 081
Revises: 080
"""

from alembic import op
import sqlalchemy as sa

revision = "081"
down_revision = "080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NLP model version tracking
    op.create_table(
        "nlp_model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("model_name", sa.String(100), nullable=False, index=True),
        sa.Column("model_type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("f1_score", sa.Float(), nullable=True),
        sa.Column("corpus_size", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1"),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Event-to-sentiment impact correlation
    op.create_table(
        "sentiment_event_impacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_description", sa.Text(), nullable=True),
        sa.Column("pre_event_sentiment", sa.Float(), nullable=True),
        sa.Column("post_event_sentiment", sa.Float(), nullable=True),
        sa.Column("sentiment_change", sa.Float(), nullable=True),
        sa.Column("price_impact_pct", sa.Float(), nullable=True),
        sa.Column("event_date", sa.DateTime(), nullable=False, index=True),
        sa.Column("measured_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sentiment_event_impacts")
    op.drop_table("nlp_model_versions")
