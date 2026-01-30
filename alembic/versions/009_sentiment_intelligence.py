"""Sentiment intelligence tables.

Revision ID: 009
Revises: 008
Create Date: 2026-01-30

Adds:
- news_articles: Scored news articles
- social_mentions: Social media ticker mentions
- insider_filings: SEC Form 4 insider trades
- analyst_ratings: Analyst ratings and targets
- earnings_transcripts: Earnings call analysis
- sentiment_scores: Composite sentiment scores
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # News articles with sentiment scores
    op.create_table(
        'news_articles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text()),
        sa.Column('source', sa.String(50)),
        sa.Column('url', sa.Text()),
        sa.Column('published_at', sa.DateTime(), index=True),
        sa.Column('symbols_json', sa.Text()),
        sa.Column('sentiment', sa.String(10)),
        sa.Column('sentiment_score', sa.Float()),
        sa.Column('confidence', sa.Float()),
        sa.Column('topic', sa.String(50)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Social media mentions
    op.create_table(
        'social_mentions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('source', sa.String(20), nullable=False),
        sa.Column('mention_count', sa.Integer()),
        sa.Column('avg_sentiment', sa.Float()),
        sa.Column('total_upvotes', sa.Integer()),
        sa.Column('total_comments', sa.Integer()),
        sa.Column('bullish_pct', sa.Float()),
        sa.Column('is_trending', sa.Boolean(), default=False),
        sa.Column('snapshot_time', sa.DateTime(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Insider filings (SEC Form 4)
    op.create_table(
        'insider_filings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('insider_name', sa.String(100)),
        sa.Column('insider_title', sa.String(50)),
        sa.Column('transaction_type', sa.String(1)),
        sa.Column('shares', sa.Integer()),
        sa.Column('price', sa.Float()),
        sa.Column('value', sa.Float()),
        sa.Column('filing_date', sa.Date(), index=True),
        sa.Column('is_10b5_1', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Analyst ratings
    op.create_table(
        'analyst_ratings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('analyst_name', sa.String(100)),
        sa.Column('firm', sa.String(100)),
        sa.Column('rating', sa.String(20)),
        sa.Column('previous_rating', sa.String(20)),
        sa.Column('target_price', sa.Float()),
        sa.Column('previous_target', sa.Float()),
        sa.Column('date', sa.Date(), index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Earnings call analysis
    op.create_table(
        'earnings_analysis',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('quarter', sa.String(10)),
        sa.Column('date', sa.Date()),
        sa.Column('management_tone', sa.Float()),
        sa.Column('qa_sentiment', sa.Float()),
        sa.Column('overall_score', sa.Float()),
        sa.Column('confidence_score', sa.Float()),
        sa.Column('guidance_direction', sa.String(20)),
        sa.Column('fog_index', sa.Float()),
        sa.Column('key_topics_json', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Composite sentiment scores
    op.create_table(
        'sentiment_scores',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('symbol', sa.String(10), nullable=False, index=True),
        sa.Column('composite_score', sa.Float()),
        sa.Column('composite_normalized', sa.Float()),
        sa.Column('news_sentiment', sa.Float()),
        sa.Column('social_sentiment', sa.Float()),
        sa.Column('insider_signal', sa.Float()),
        sa.Column('analyst_revision', sa.Float()),
        sa.Column('earnings_tone', sa.Float()),
        sa.Column('options_flow', sa.Float()),
        sa.Column('confidence', sa.String(10)),
        sa.Column('sources_available', sa.Integer()),
        sa.Column('computed_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table('sentiment_scores')
    op.drop_table('earnings_analysis')
    op.drop_table('analyst_ratings')
    op.drop_table('insider_filings')
    op.drop_table('social_mentions')
    op.drop_table('news_articles')
