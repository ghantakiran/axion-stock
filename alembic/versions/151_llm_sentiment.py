"""PRD-151: LLM Sentiment Engine tables.

Revision ID: 151
Revises: 150
"""

from alembic import op
import sqlalchemy as sa

revision = "151"
down_revision = "150"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # LLM sentiment analysis results
    op.create_table(
        "llm_sentiment_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("result_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("text_hash", sa.String(64), index=True, nullable=False),
        sa.Column("text_preview", sa.Text),
        sa.Column("sentiment", sa.String(20), nullable=False, index=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("reasoning", sa.Text),
        sa.Column("themes_json", sa.Text),
        sa.Column("tickers_json", sa.Text),
        sa.Column("urgency", sa.String(20)),
        sa.Column("time_horizon", sa.String(20)),
        sa.Column("model_used", sa.String(100)),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Float),
        sa.Column("source_type", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Entity-level sentiment
    op.create_table(
        "llm_entity_sentiments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("result_id", sa.String(50), index=True, nullable=False),
        sa.Column("entity_name", sa.String(200), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False, index=True),
        sa.Column("ticker", sa.String(20), index=True),
        sa.Column("sentiment", sa.String(20), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("context", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Sentiment forecasts
    op.create_table(
        "llm_sentiment_forecasts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("forecast_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("horizon", sa.String(10), nullable=False),
        sa.Column("current_score", sa.Float),
        sa.Column("predicted_score", sa.Float),
        sa.Column("predicted_direction", sa.String(20)),
        sa.Column("confidence", sa.Float),
        sa.Column("momentum", sa.Float),
        sa.Column("reversal_probability", sa.Float),
        sa.Column("half_life_hours", sa.Float),
        sa.Column("observation_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("llm_sentiment_forecasts")
    op.drop_table("llm_entity_sentiments")
    op.drop_table("llm_sentiment_results")
