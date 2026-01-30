"""Enterprise platform database schema.

Revision ID: 010_enterprise_platform
Revises: 009_backtesting_system
Create Date: 2026-01-28

Tables:
- users: User accounts with auth and subscription
- sessions: Active user sessions
- api_keys: API keys for programmatic access
- accounts: Trading accounts
- account_snapshots: Point-in-time account values
- workspaces: Team workspaces
- workspace_members: Workspace membership
- shared_strategies: Strategies shared in workspaces
- activity_feed: Workspace activity feed
- audit_log: Comprehensive audit trail
- compliance_rules: Compliance rule definitions
- compliance_violations: Violation records
- restricted_securities: Restricted trading list
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, INET, ARRAY

revision = '010_enterprise_platform'
down_revision = '009_backtesting_system'
branch_labels = None
depends_on = None


def upgrade():
    # ==========================================================================
    # users - User accounts
    # ==========================================================================
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.Text(), unique=True, nullable=False),
        sa.Column('password_hash', sa.Text()),
        sa.Column('name', sa.Text()),
        sa.Column('role', sa.String(20), default='trader'),
        sa.Column('subscription', sa.String(20), default='free'),
        
        # Profile
        sa.Column('avatar_url', sa.Text()),
        sa.Column('timezone', sa.String(50), default='UTC'),
        sa.Column('preferences', JSONB, default={}),
        
        # OAuth
        sa.Column('google_id', sa.String(128)),
        sa.Column('github_id', sa.String(128)),
        sa.Column('apple_id', sa.String(128)),
        
        # 2FA
        sa.Column('totp_secret', sa.String(64)),
        sa.Column('totp_enabled', sa.Boolean(), default=False),
        
        # Status
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('email_verified_at', sa.DateTime(timezone=True)),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(timezone=True)),
    )
    
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_subscription', 'users', ['subscription'])
    
    # ==========================================================================
    # sessions - Active user sessions
    # ==========================================================================
    op.create_table(
        'sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=False),
        sa.Column('ip_address', INET),
        sa.Column('user_agent', sa.Text()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('last_activity_at', sa.DateTime(timezone=True)),
    )
    
    op.create_index('ix_sessions_user', 'sessions', ['user_id'])
    op.create_index('ix_sessions_token', 'sessions', ['access_token'])
    
    # ==========================================================================
    # api_keys - API keys for programmatic access
    # ==========================================================================
    op.create_table(
        'api_keys',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False),
        sa.Column('key_prefix', sa.String(12), nullable=False),
        sa.Column('scopes', ARRAY(sa.String(64))),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('request_count', sa.BigInteger(), default=0),
    )
    
    op.create_index('ix_api_keys_user', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_hash', 'api_keys', ['key_hash'])
    
    # ==========================================================================
    # accounts - Trading accounts
    # ==========================================================================
    op.create_table(
        'accounts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('account_type', sa.String(32), nullable=False),
        sa.Column('broker', sa.String(32), default='paper'),
        sa.Column('broker_account_id', sa.String(128)),
        
        # Strategy
        sa.Column('strategy_id', UUID(as_uuid=True)),
        sa.Column('strategy_name', sa.String(128)),
        sa.Column('target_allocation', JSONB, default={}),
        
        # Financials
        sa.Column('cash_balance', sa.Float(), default=0),
        sa.Column('total_value', sa.Float(), default=0),
        sa.Column('cost_basis', sa.Float(), default=0),
        
        # Tax
        sa.Column('tax_status', sa.String(20), default='taxable'),
        
        # Benchmark
        sa.Column('benchmark', sa.String(16), default='SPY'),
        
        # Dates
        sa.Column('inception_date', sa.Date()),
        
        # Status
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_primary', sa.Boolean(), default=False),
        
        # Permissions
        sa.Column('permissions', ARRAY(UUID(as_uuid=True))),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index('ix_accounts_owner', 'accounts', ['owner_id'])
    op.create_index('ix_accounts_type', 'accounts', ['account_type'])
    
    # ==========================================================================
    # account_snapshots - Point-in-time account values
    # ==========================================================================
    op.create_table(
        'account_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_value', sa.Float(), nullable=False),
        sa.Column('cash_balance', sa.Float()),
        sa.Column('positions_value', sa.Float()),
        sa.Column('day_pnl', sa.Float()),
        sa.Column('total_pnl', sa.Float()),
        sa.Column('positions', JSONB),
    )
    
    op.create_index('ix_account_snapshots_account_time', 'account_snapshots', ['account_id', 'timestamp'])
    
    # ==========================================================================
    # workspaces - Team workspaces
    # ==========================================================================
    op.create_table(
        'workspaces',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('settings', JSONB, default={}),
        sa.Column('logo_url', sa.Text()),
        sa.Column('member_count', sa.Integer(), default=0),
        sa.Column('strategy_count', sa.Integer(), default=0),
        sa.Column('total_aum', sa.Float(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index('ix_workspaces_owner', 'workspaces', ['owner_id'])
    
    # ==========================================================================
    # workspace_members - Workspace membership
    # ==========================================================================
    op.create_table(
        'workspace_members',
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('role', sa.String(20), default='member'),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('invited_by', UUID(as_uuid=True)),
    )
    
    # ==========================================================================
    # shared_strategies - Strategies shared in workspaces
    # ==========================================================================
    op.create_table(
        'shared_strategies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('creator_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('config', JSONB, default={}),
        sa.Column('ytd_return', sa.Float(), default=0),
        sa.Column('sharpe_ratio', sa.Float(), default=0),
        sa.Column('total_return', sa.Float(), default=0),
        sa.Column('use_count', sa.Integer(), default=0),
        sa.Column('fork_count', sa.Integer(), default=0),
        sa.Column('is_public', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index('ix_shared_strategies_workspace', 'shared_strategies', ['workspace_id'])
    
    # ==========================================================================
    # activity_feed - Workspace activity feed
    # ==========================================================================
    op.create_table(
        'activity_feed',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('user_name', sa.String(128)),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('resource_type', sa.String(32)),
        sa.Column('resource_id', sa.String(64)),
        sa.Column('resource_name', sa.String(128)),
        sa.Column('details', JSONB),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index('ix_activity_feed_workspace', 'activity_feed', ['workspace_id', 'timestamp'])
    
    # ==========================================================================
    # audit_log - Comprehensive audit trail
    # ==========================================================================
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True)),
        sa.Column('user_email', sa.Text()),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('resource_type', sa.String(32)),
        sa.Column('resource_id', sa.String(64)),
        sa.Column('details', JSONB),
        sa.Column('ip_address', INET),
        sa.Column('user_agent', sa.Text()),
        sa.Column('status', sa.String(20), default='success'),
        sa.Column('error_message', sa.Text()),
    )
    
    op.create_index('ix_audit_log_user', 'audit_log', ['user_id'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])
    op.create_index('ix_audit_log_timestamp', 'audit_log', ['timestamp'])
    op.create_index('ix_audit_log_resource', 'audit_log', ['resource_type', 'resource_id'])
    
    # ==========================================================================
    # compliance_rules - Compliance rule definitions
    # ==========================================================================
    op.create_table(
        'compliance_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('rule_type', sa.String(64), nullable=False),
        sa.Column('parameters', JSONB, default={}),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # ==========================================================================
    # compliance_violations - Violation records
    # ==========================================================================
    op.create_table(
        'compliance_violations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('rule_id', UUID(as_uuid=True), sa.ForeignKey('compliance_rules.id', ondelete='SET NULL')),
        sa.Column('rule_name', sa.String(128)),
        sa.Column('account_id', UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('violation_type', sa.String(64)),
        sa.Column('details', JSONB),
        sa.Column('severity', sa.String(20), default='warning'),
        sa.Column('is_resolved', sa.Boolean(), default=False),
        sa.Column('resolved_by', UUID(as_uuid=True)),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    op.create_index('ix_compliance_violations_account', 'compliance_violations', ['account_id'])
    op.create_index('ix_compliance_violations_unresolved', 'compliance_violations', ['is_resolved', 'timestamp'])
    
    # ==========================================================================
    # restricted_securities - Restricted trading list
    # ==========================================================================
    op.create_table(
        'restricted_securities',
        sa.Column('symbol', sa.String(16), primary_key=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('restricted_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL')),
        sa.Column('restriction_type', sa.String(20), default='all'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date()),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('restricted_securities')
    op.drop_table('compliance_violations')
    op.drop_table('compliance_rules')
    op.drop_table('audit_log')
    op.drop_table('activity_feed')
    op.drop_table('shared_strategies')
    op.drop_table('workspace_members')
    op.drop_table('workspaces')
    op.drop_table('account_snapshots')
    op.drop_table('accounts')
    op.drop_table('api_keys')
    op.drop_table('sessions')
    op.drop_table('users')
