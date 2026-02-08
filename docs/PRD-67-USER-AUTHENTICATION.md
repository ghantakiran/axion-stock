# PRD-67: User Authentication & RBAC

## Overview
Full-featured authentication system with password hashing, JWT tokens, TOTP 2FA, OAuth providers, role-based access control, API key management, and rate limiting.

## Components

### 1. Auth Service (`src/enterprise/auth.py`)
- **PasswordHasher** — PBKDF2 with 100,000 iterations (SHA256), secure salt generation
- **TokenManager** — Custom JWT-like tokens with HMAC-SHA256 signatures, configurable expiration, refresh token support
- **TOTPManager** — TOTP 2FA with 6-digit codes, 30-second intervals, provisioning URI for authenticator apps
- **AuthService** — Full orchestration: registration, login (with 2FA), session management, token refresh, permission checking, feature access by subscription tier, API key CRUD, 2FA enable/disable

### 2. OAuth Integration (`src/enterprise/oauth.py`)
- **GoogleOAuthProvider** — Full Google OAuth 2.0 flow (authorization URL, code exchange, user info)
- **GitHubOAuthProvider** — Full GitHub OAuth flow (authorization, token exchange, user/email retrieval)
- **OAuthService** — State token management (10-min expiry), provider routing, callback handling
- **RateLimiter** — OAuth endpoint rate limiting (10 attempts/minute)

### 3. API Key Management (`src/api/auth.py`)
- **APIKeyManager** — Key generation (`ax_` prefix), SHA256 hashing, scope-based access control, revocation
- **RateLimiter** — Token bucket rate limiting per tier (FREE: 10/min, PRO: 60/min, ENTERPRISE: 600/min)
- **WebhookSigner** — HMAC webhook signing for outbound security

### 4. Configuration (`src/enterprise/config.py`)
- **UserRole** — VIEWER, TRADER, MANAGER, ADMIN with permission mappings
- **SubscriptionTier** — FREE, PRO, ENTERPRISE with feature gates
- Role-to-permissions mapping (4 roles x 4-15 permissions)

### 5. User Models (`src/enterprise/models.py`)
- **User** — Email, password_hash, name, role, subscription, OAuth IDs (Google/GitHub/Apple), TOTP, status flags
- **Session** — Access/refresh tokens, device info, lifecycle tracking
- **APIKey** — Key hash, prefix, scopes, usage tracking, expiration

## Database Tables
- `users` — User accounts with auth fields and OAuth IDs
- `user_sessions` — Session management with hashed tokens
- `user_api_keys` — API key storage with scopes
- `user_audit_logs` — Comprehensive audit trail
- `oauth_states` — OAuth state token management
- `rate_limit_records` — Rate limiting enforcement
- `password_reset_tokens` — Password reset token tracking
- `email_verification_tokens` — Email verification tokens

## Dashboard
Streamlit auth dashboard (`app/pages/auth.py`):
- Login/registration forms with password validation
- Profile management (avatar, name, timezone)
- Security settings (password change, 2FA toggle with QR)
- API key management interface
- Active session management (view/revoke)
- Subscription tier display with feature comparison
- Role & permissions display

## Test Coverage
Comprehensive tests in `tests/test_authentication.py` covering password hashing, JWT tokens, TOTP, OAuth, rate limiting, RBAC, sessions, API keys, and validation.
