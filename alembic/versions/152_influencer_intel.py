"""PRD-152: Influencer Intelligence Platform tables.

Revision ID: 152
Revises: 151
"""

from alembic import op
import sqlalchemy as sa

revision = "152"
down_revision = "151"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Influencer profiles (persistent)
    op.create_table(
        "influencer_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("author_id", sa.String(100), nullable=False, index=True),
        sa.Column("platform", sa.String(30), nullable=False, index=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("total_posts", sa.Integer),
        sa.Column("total_upvotes", sa.Integer),
        sa.Column("accuracy_rate", sa.Float),
        sa.Column("impact_score", sa.Float),
        sa.Column("discovery_score", sa.Float),
        sa.Column("top_tickers_json", sa.Text),
        sa.Column("sector_accuracy_json", sa.Text),
        sa.Column("first_seen", sa.DateTime(timezone=True)),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Prediction records
    op.create_table(
        "influencer_predictions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("prediction_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("author_id", sa.String(100), nullable=False, index=True),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("sentiment_score", sa.Float),
        sa.Column("entry_price", sa.Float),
        sa.Column("exit_price", sa.Float),
        sa.Column("actual_return_pct", sa.Float),
        sa.Column("was_correct", sa.Boolean),
        sa.Column("sector", sa.String(50)),
        sa.Column("predicted_at", sa.DateTime(timezone=True)),
        sa.Column("evaluated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Network clusters
    op.create_table(
        "influencer_clusters",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("cluster_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("members_json", sa.Text, nullable=False),
        sa.Column("shared_tickers_json", sa.Text),
        sa.Column("avg_sentiment", sa.Float),
        sa.Column("coordination_score", sa.Float),
        sa.Column("size", sa.Integer),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("influencer_clusters")
    op.drop_table("influencer_predictions")
    op.drop_table("influencer_profiles")
