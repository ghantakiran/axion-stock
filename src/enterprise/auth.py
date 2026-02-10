"""Authentication System.

Handles user authentication, JWT tokens, password hashing,
2FA, and session management.
"""

import hashlib
import hmac
import logging
import secrets
import base64
from datetime import datetime, timedelta
from typing import Optional, Tuple
import json

from src.enterprise.config import (
    AuthConfig, DEFAULT_AUTH_CONFIG,
    UserRole, ROLE_PERMISSIONS, SubscriptionTier, SUBSCRIPTION_LIMITS,
)
from src.enterprise.models import User, Session, APIKey, generate_uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Password Hashing (bcrypt-compatible using hashlib for portability)
# =============================================================================


class PasswordHasher:
    """Password hashing using PBKDF2 (bcrypt-compatible interface)."""

    def __init__(self, iterations: int = 100_000):
        self.iterations = iterations

    def hash(self, password: str) -> str:
        """Hash a password.

        Args:
            password: Plain text password.

        Returns:
            Hashed password string.
        """
        salt = secrets.token_bytes(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            self.iterations,
        )
        # Store as: iterations$salt$hash (base64 encoded)
        return f"{self.iterations}${base64.b64encode(salt).decode()}${base64.b64encode(key).decode()}"

    def verify(self, password: str, hash_str: str) -> bool:
        """Verify a password against a hash.

        Args:
            password: Plain text password to verify.
            hash_str: Previously hashed password.

        Returns:
            True if password matches.
        """
        try:
            iterations, salt_b64, hash_b64 = hash_str.split('$')
            salt = base64.b64decode(salt_b64)
            stored_hash = base64.b64decode(hash_b64)

            key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                int(iterations),
            )
            return hmac.compare_digest(key, stored_hash)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False


# =============================================================================
# JWT Token Management
# =============================================================================


class TokenManager:
    """JWT-like token management using HMAC."""

    def __init__(self, config: Optional[AuthConfig] = None):
        self.config = config or DEFAULT_AUTH_CONFIG
        self.secret_key = self.config.jwt_secret_key.encode()

    def create_access_token(
        self,
        user_id: str,
        role: UserRole,
        extra_claims: Optional[dict] = None,
    ) -> str:
        """Create an access token.

        Args:
            user_id: User ID to encode.
            role: User role.
            extra_claims: Additional claims to include.

        Returns:
            Encoded token string.
        """
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "role": role.value,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + self.config.access_token_expire).timestamp()),
            "jti": generate_uuid(),
        }
        if extra_claims:
            payload.update(extra_claims)

        return self._encode_token(payload)

    def create_refresh_token(self, user_id: str) -> str:
        """Create a refresh token.

        Args:
            user_id: User ID to encode.

        Returns:
            Encoded refresh token string.
        """
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + self.config.refresh_token_expire).timestamp()),
            "jti": generate_uuid(),
        }
        return self._encode_token(payload)

    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate a token.

        Args:
            token: Token string to decode.

        Returns:
            Decoded payload dict, or None if invalid.
        """
        try:
            parts = token.split('.')
            if len(parts) != 2:
                return None

            payload_b64, signature = parts

            # Verify signature
            expected_sig = self._sign(payload_b64)
            if not hmac.compare_digest(signature, expected_sig):
                return None

            # Decode payload
            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + '=='))

            # Check expiration
            if payload.get('exp', 0) < datetime.utcnow().timestamp():
                return None

            return payload

        except Exception as e:
            logger.debug(f"Token decode error: {e}")
            return None

    def _encode_token(self, payload: dict) -> str:
        """Encode a payload into a token."""
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip('=')

        signature = self._sign(payload_b64)
        return f"{payload_b64}.{signature}"

    def _sign(self, data: str) -> str:
        """Create HMAC signature."""
        sig = hmac.new(
            self.secret_key,
            data.encode(),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(sig).decode().rstrip('=')


# =============================================================================
# Two-Factor Authentication
# =============================================================================


class TOTPManager:
    """Time-based One-Time Password (TOTP) for 2FA."""

    def __init__(self, digits: int = 6, interval: int = 30):
        self.digits = digits
        self.interval = interval

    def generate_secret(self) -> str:
        """Generate a new TOTP secret.

        Returns:
            Base32-encoded secret.
        """
        secret = secrets.token_bytes(20)
        return base64.b32encode(secret).decode()

    def generate_code(self, secret: str, timestamp: Optional[int] = None) -> str:
        """Generate a TOTP code.

        Args:
            secret: Base32-encoded secret.
            timestamp: Unix timestamp (default: now).

        Returns:
            TOTP code string.
        """
        if timestamp is None:
            timestamp = int(datetime.utcnow().timestamp())

        counter = timestamp // self.interval

        # Decode secret
        key = base64.b32decode(secret.upper())

        # Generate HMAC
        counter_bytes = counter.to_bytes(8, 'big')
        hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

        # Dynamic truncation
        offset = hmac_hash[-1] & 0x0f
        code = (
            ((hmac_hash[offset] & 0x7f) << 24) |
            ((hmac_hash[offset + 1] & 0xff) << 16) |
            ((hmac_hash[offset + 2] & 0xff) << 8) |
            (hmac_hash[offset + 3] & 0xff)
        )

        return str(code % (10 ** self.digits)).zfill(self.digits)

    def verify_code(self, secret: str, code: str, window: int = 1) -> bool:
        """Verify a TOTP code.

        Args:
            secret: Base32-encoded secret.
            code: Code to verify.
            window: Number of intervals to check before/after.

        Returns:
            True if code is valid.
        """
        timestamp = int(datetime.utcnow().timestamp())

        for offset in range(-window, window + 1):
            check_time = timestamp + (offset * self.interval)
            expected = self.generate_code(secret, check_time)
            if hmac.compare_digest(code, expected):
                return True

        return False

    def get_provisioning_uri(
        self,
        secret: str,
        email: str,
        issuer: str = "Axion",
    ) -> str:
        """Generate a provisioning URI for authenticator apps.

        Args:
            secret: Base32-encoded secret.
            email: User email.
            issuer: Application name.

        Returns:
            otpauth:// URI.
        """
        from urllib.parse import quote
        return (
            f"otpauth://totp/{quote(issuer)}:{quote(email)}"
            f"?secret={secret}&issuer={quote(issuer)}&digits={self.digits}"
        )


# =============================================================================
# Authentication Service
# =============================================================================


class AuthService:
    """Main authentication service.

    Handles login, registration, session management, and authorization.
    """

    def __init__(self, config: Optional[AuthConfig] = None):
        self.config = config or DEFAULT_AUTH_CONFIG
        self.password_hasher = PasswordHasher()
        self.token_manager = TokenManager(config)
        self.totp_manager = TOTPManager()

        # In-memory stores (replace with database in production)
        self._users: dict[str, User] = {}
        self._sessions: dict[str, Session] = {}
        self._api_keys: dict[str, APIKey] = {}

    def register(
        self,
        email: str,
        password: str,
        name: str = "",
        role: UserRole = UserRole.TRADER,
    ) -> Tuple[Optional[User], Optional[str]]:
        """Register a new user.

        Args:
            email: User email.
            password: Plain text password.
            name: User name.
            role: User role.

        Returns:
            Tuple of (User, error_message).
        """
        # Validate email
        if not self._validate_email(email):
            return None, "Invalid email format"

        # Check if email exists
        for user in self._users.values():
            if user.email.lower() == email.lower():
                return None, "Email already registered"

        # Validate password
        valid, msg = self._validate_password(password)
        if not valid:
            return None, msg

        # Create user
        user = User(
            email=email.lower(),
            password_hash=self.password_hasher.hash(password),
            name=name,
            role=role,
        )

        self._users[user.id] = user
        logger.info(f"User registered: {user.email}")

        return user, None

    # ── Login rate limiting ──────────────────────────────────────
    _MAX_FAILED_ATTEMPTS = 5
    _LOCKOUT_MINUTES = 15
    _MAX_SESSIONS_PER_USER = 10

    def login(
        self,
        email: str,
        password: str,
        totp_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[Optional[Session], Optional[str]]:
        """Log in a user.

        Args:
            email: User email.
            password: Plain text password.
            totp_code: 2FA code if enabled.
            ip_address: Client IP address.
            user_agent: Client user agent.

        Returns:
            Tuple of (Session, error_message).
        """
        # Check login rate limit
        if not hasattr(self, "_failed_attempts"):
            self._failed_attempts: dict = {}  # email -> (count, first_failure_time)

        email_lower = email.lower()
        if email_lower in self._failed_attempts:
            count, first_time = self._failed_attempts[email_lower]
            elapsed = (datetime.utcnow() - first_time).total_seconds() / 60
            if count >= self._MAX_FAILED_ATTEMPTS and elapsed < self._LOCKOUT_MINUTES:
                remaining = int(self._LOCKOUT_MINUTES - elapsed)
                return None, f"Account locked — too many failed attempts. Try again in {remaining} min"
            if elapsed >= self._LOCKOUT_MINUTES:
                del self._failed_attempts[email_lower]

        # Find user
        user = None
        for u in self._users.values():
            if u.email.lower() == email_lower:
                user = u
                break

        if not user:
            self._record_failed_attempt(email_lower)
            return None, "Invalid credentials"

        if not user.is_active:
            return None, "Account is disabled"

        # Verify password
        if not self.password_hasher.verify(password, user.password_hash):
            self._record_failed_attempt(email_lower)
            return None, "Invalid credentials"

        # Clear failed attempts on success
        self._failed_attempts.pop(email_lower, None)

        # Check 2FA
        if user.totp_enabled:
            if not totp_code:
                return None, "2FA code required"
            if not self.totp_manager.verify_code(user.totp_secret, totp_code):
                return None, "Invalid 2FA code"

        # Enforce session limit — evict oldest sessions
        user_sessions = [
            s for s in self._sessions.values()
            if s.user_id == user.id and s.is_active
        ]
        if len(user_sessions) >= self._MAX_SESSIONS_PER_USER:
            oldest = sorted(user_sessions, key=lambda s: s.created_at or datetime.min)
            for old_sess in oldest[: len(user_sessions) - self._MAX_SESSIONS_PER_USER + 1]:
                old_sess.is_active = False

        # Create session
        session = Session(
            user_id=user.id,
            access_token=self.token_manager.create_access_token(user.id, user.role),
            refresh_token=self.token_manager.create_refresh_token(user.id),
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + self.config.refresh_token_expire,
        )

        self._sessions[session.id] = session

        # Update user
        user.last_login_at = datetime.utcnow()

        logger.info(f"User logged in: {user.email}")
        return session, None

    def _record_failed_attempt(self, email_lower: str) -> None:
        """Track failed login attempts for rate limiting."""
        if email_lower in self._failed_attempts:
            count, first_time = self._failed_attempts[email_lower]
            self._failed_attempts[email_lower] = (count + 1, first_time)
        else:
            self._failed_attempts[email_lower] = (1, datetime.utcnow())

    def logout(self, session_id: str) -> bool:
        """Log out a session.

        Args:
            session_id: Session ID to invalidate.

        Returns:
            True if successful.
        """
        if session_id in self._sessions:
            self._sessions[session_id].is_active = False
            return True
        return False

    def refresh_token(self, refresh_token: str) -> Tuple[Optional[str], Optional[str]]:
        """Refresh an access token.

        Args:
            refresh_token: Valid refresh token.

        Returns:
            Tuple of (new_access_token, error_message).
        """
        payload = self.token_manager.decode_token(refresh_token)
        if not payload:
            return None, "Invalid refresh token"

        if payload.get('type') != 'refresh':
            return None, "Invalid token type"

        user_id = payload.get('sub')
        user = self._users.get(user_id)
        if not user or not user.is_active:
            return None, "User not found or inactive"

        new_token = self.token_manager.create_access_token(user.id, user.role)
        return new_token, None

    def verify_token(self, token: str) -> Tuple[Optional[User], Optional[str]]:
        """Verify an access token and return the user.

        Args:
            token: Access token to verify.

        Returns:
            Tuple of (User, error_message).
        """
        payload = self.token_manager.decode_token(token)
        if not payload:
            return None, "Invalid token"

        if payload.get('type') != 'access':
            return None, "Invalid token type"

        user_id = payload.get('sub')
        user = self._users.get(user_id)
        if not user:
            return None, "User not found"

        if not user.is_active:
            return None, "User is disabled"

        return user, None

    def has_permission(self, user: User, permission: str) -> bool:
        """Check if user has a specific permission.

        Args:
            user: User to check.
            permission: Permission string.

        Returns:
            True if user has permission.
        """
        role_perms = ROLE_PERMISSIONS.get(user.role, set())
        return permission in role_perms

    def check_feature_access(
        self,
        user: User,
        feature: str,
    ) -> Tuple[bool, Optional[str]]:
        """Check if user's subscription allows a feature.

        Args:
            user: User to check.
            feature: Feature name.

        Returns:
            Tuple of (allowed, upgrade_message).
        """
        limits = SUBSCRIPTION_LIMITS.get(user.subscription, {})
        value = limits.get(feature)

        if value is False:
            return False, f"Upgrade to Pro for {feature}"
        if value == 0:
            return False, f"Upgrade to Pro for {feature}"

        return True, None

    def enable_totp(self, user_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Enable 2FA for a user.

        Args:
            user_id: User ID.

        Returns:
            Tuple of (secret, error_message).
        """
        user = self._users.get(user_id)
        if not user:
            return None, "User not found"

        secret = self.totp_manager.generate_secret()
        user.totp_secret = secret
        # Don't enable until verified
        return secret, None

    def confirm_totp(self, user_id: str, code: str) -> Tuple[bool, Optional[str]]:
        """Confirm and enable 2FA.

        Args:
            user_id: User ID.
            code: TOTP code to verify.

        Returns:
            Tuple of (success, error_message).
        """
        user = self._users.get(user_id)
        if not user or not user.totp_secret:
            return False, "TOTP not set up"

        if self.totp_manager.verify_code(user.totp_secret, code):
            user.totp_enabled = True
            return True, None

        return False, "Invalid code"

    def create_api_key(
        self,
        user_id: str,
        name: str,
        scopes: list[str],
        expires_in_days: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[APIKey], Optional[str]]:
        """Create an API key.

        Args:
            user_id: User ID.
            name: Key name.
            scopes: List of scopes.
            expires_in_days: Days until expiration.

        Returns:
            Tuple of (raw_key, api_key_object, error_message).
        """
        user = self._users.get(user_id)
        if not user:
            return None, None, "User not found"

        # Generate key
        raw_key = f"axn_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        api_key = APIKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=raw_key[:12],
            scopes=scopes,
            expires_at=(
                datetime.utcnow() + timedelta(days=expires_in_days)
                if expires_in_days else None
            ),
        )

        self._api_keys[api_key.id] = api_key

        # Return raw key only once
        return raw_key, api_key, None

    def verify_api_key(self, raw_key: str) -> Tuple[Optional[User], Optional[str]]:
        """Verify an API key.

        Args:
            raw_key: Raw API key.

        Returns:
            Tuple of (User, error_message).
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        for api_key in self._api_keys.values():
            if api_key.key_hash == key_hash:
                if not api_key.is_active:
                    return None, "API key is revoked"

                if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                    return None, "API key has expired"

                user = self._users.get(api_key.user_id)
                if not user:
                    return None, "User not found"

                # Update usage stats
                api_key.last_used_at = datetime.utcnow()
                api_key.request_count += 1

                return user, None

        return None, "Invalid API key"

    def _validate_email(self, email: str) -> bool:
        """Basic email validation."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _validate_password(self, password: str) -> Tuple[bool, str]:
        """Validate password strength."""
        if len(password) < self.config.password_min_length:
            return False, f"Password must be at least {self.config.password_min_length} characters"

        if self.config.password_require_uppercase and not any(c.isupper() for c in password):
            return False, "Password must contain an uppercase letter"

        if self.config.password_require_lowercase and not any(c.islower() for c in password):
            return False, "Password must contain a lowercase letter"

        if self.config.password_require_digit and not any(c.isdigit() for c in password):
            return False, "Password must contain a digit"

        return True, ""

    # User CRUD helpers
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        for user in self._users.values():
            if user.email.lower() == email.lower():
                return user
        return None

    def update_user(self, user_id: str, **kwargs) -> Optional[User]:
        """Update user fields."""
        user = self._users.get(user_id)
        if not user:
            return None

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        user.updated_at = datetime.utcnow()
        return user
