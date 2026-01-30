"""ML prediction engine tables.

Revision ID: 007
Revises: 006
Create Date: 2026-01-29

Adds:
- ml_models: Model registry
- ml_predictions: Prediction history
- ml_training_runs: Training run log
- ml_feature_drift: Feature drift tracking
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Model registry
    op.create_table(
        'ml_models',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('model_name', sa.String(100), nullable=False, index=True),
        sa.Column('model_version', sa.String(50), nullable=False),
        sa.Column('model_type', sa.String(50)),  # ranking, regime, earnings, factor_timing
        sa.Column('status', sa.String(20), default='trained'),  # trained, production, deprecated
        sa.Column('trained_at', sa.DateTime, nullable=False),
        sa.Column('train_start', sa.Date),
        sa.Column('train_end', sa.Date),
        sa.Column('n_train_samples', sa.Integer),
        sa.Column('n_features', sa.Integer),
        sa.Column('feature_names', sa.Text),  # JSON
        sa.Column('hyperparameters', sa.Text),  # JSON
        sa.Column('metrics', sa.Text),  # JSON
        sa.Column('walk_forward_metrics', sa.Text),  # JSON
        sa.Column('model_path', sa.String(500)),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_ml_models_name_version', 'ml_models', ['model_name', 'model_version'], unique=True)
    op.create_index('ix_ml_models_status', 'ml_models', ['status'])

    # Prediction history
    op.create_table(
        'ml_predictions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('model_name', sa.String(100), nullable=False, index=True),
        sa.Column('prediction_date', sa.Date, nullable=False, index=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('predicted_score', sa.Float),
        sa.Column('predicted_quintile', sa.Integer),
        sa.Column('predicted_regime', sa.String(20)),
        sa.Column('beat_probability', sa.Float),
        sa.Column('confidence', sa.Float),
        sa.Column('actual_return', sa.Float),
        sa.Column('actual_quintile', sa.Integer),
        sa.Column('actual_recorded_at', sa.DateTime),
        sa.Column('feature_values', sa.Text),  # JSON of top features
        sa.Column('explanation', sa.Text),  # JSON of SHAP values
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_predictions_date_model', 'ml_predictions', ['prediction_date', 'model_name'])
    op.create_index('ix_predictions_symbol_date', 'ml_predictions', ['symbol', 'prediction_date'])

    # Training run log
    op.create_table(
        'ml_training_runs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.String(100), unique=True, nullable=False),
        sa.Column('model_name', sa.String(100), nullable=False, index=True),
        sa.Column('model_version', sa.String(50)),
        sa.Column('status', sa.String(20), nullable=False),  # running, completed, failed
        sa.Column('started_at', sa.DateTime, nullable=False),
        sa.Column('completed_at', sa.DateTime),
        sa.Column('duration_seconds', sa.Float),
        sa.Column('train_samples', sa.Integer),
        sa.Column('val_samples', sa.Integer),
        sa.Column('n_features', sa.Integer),
        sa.Column('hyperparameters', sa.Text),  # JSON
        sa.Column('metrics', sa.Text),  # JSON
        sa.Column('walk_forward_results', sa.Text),  # JSON
        sa.Column('error_message', sa.Text),
        sa.Column('trigger', sa.String(50)),  # scheduled, manual, degradation
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Feature drift tracking
    op.create_table(
        'ml_feature_drift',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('check_date', sa.Date, nullable=False, index=True),
        sa.Column('model_name', sa.String(100), nullable=False, index=True),
        sa.Column('overall_drift', sa.String(20)),  # none, minor, significant, critical
        sa.Column('n_drifted_features', sa.Integer),
        sa.Column('drifted_features', sa.Text),  # JSON
        sa.Column('psi_scores', sa.Text),  # JSON
        sa.Column('message', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Model performance metrics (rolling IC etc.)
    op.create_table(
        'ml_performance_metrics',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('metric_date', sa.Date, nullable=False, index=True),
        sa.Column('model_name', sa.String(100), nullable=False, index=True),
        sa.Column('information_coefficient', sa.Float),
        sa.Column('ic_3m_rolling', sa.Float),
        sa.Column('ic_6m_rolling', sa.Float),
        sa.Column('top_quintile_return', sa.Float),
        sa.Column('bottom_quintile_return', sa.Float),
        sa.Column('long_short_spread', sa.Float),
        sa.Column('model_accuracy', sa.Float),
        sa.Column('model_status', sa.String(20)),  # healthy, warning, degraded
        sa.Column('needs_retraining', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_perf_metrics_date_model', 'ml_performance_metrics', ['metric_date', 'model_name'])


def downgrade() -> None:
    op.drop_table('ml_performance_metrics')
    op.drop_table('ml_feature_drift')
    op.drop_table('ml_training_runs')
    op.drop_table('ml_predictions')
    op.drop_table('ml_models')
