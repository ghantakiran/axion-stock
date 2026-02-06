"""OAuth Service - Social Login Providers.

Supports:
- Google OAuth 2.0
- GitHub OAuth
- Apple Sign In (structure only)
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import urlencode

from src.enterprise.config import AuthConfig, DEFAULT_AUTH_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class OAuthUserInfo:
    """User info returned from OAuth provider."""

    provider: str
    provider_id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    email_verified: bool = False


@dataclass
class OAuthToken:
    """OAuth tokens from provider."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None


class OAuthProvider:
    """Base OAuth provider."""

    name: str = "base"
    authorize_url: str = ""
    token_url: str = ""
    userinfo_url: str = ""
    scopes: list[str] = []

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def get_authorize_url(self, state: str) -> str:
        """Get authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> Optional[OAuthToken]:
        """Exchange authorization code for tokens."""
        raise NotImplementedError

    async def get_user_info(self, token: OAuthToken) -> Optional[OAuthUserInfo]:
        """Get user info from provider."""
        raise NotImplementedError


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth 2.0 provider."""

    name = "google"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    scopes = ["openid", "email", "profile"]

    def get_authorize_url(self, state: str) -> str:
        """Get Google authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> Optional[OAuthToken]:
        """Exchange code for Google tokens."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri,
                    },
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Google token exchange failed: {await resp.text()}")
                        return None

                    data = await resp.json()
                    return OAuthToken(
                        access_token=data["access_token"],
                        token_type=data.get("token_type", "Bearer"),
                        expires_in=data.get("expires_in"),
                        refresh_token=data.get("refresh_token"),
                        scope=data.get("scope"),
                    )
        except Exception as e:
            logger.error(f"Google token exchange error: {e}")
            return None

    async def get_user_info(self, token: OAuthToken) -> Optional[OAuthUserInfo]:
        """Get user info from Google."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.userinfo_url,
                    headers={"Authorization": f"Bearer {token.access_token}"},
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Google userinfo failed: {await resp.text()}")
                        return None

                    data = await resp.json()
                    return OAuthUserInfo(
                        provider="google",
                        provider_id=data["id"],
                        email=data["email"],
                        name=data.get("name", ""),
                        avatar_url=data.get("picture"),
                        email_verified=data.get("verified_email", False),
                    )
        except Exception as e:
            logger.error(f"Google userinfo error: {e}")
            return None


class GitHubOAuthProvider(OAuthProvider):
    """GitHub OAuth provider."""

    name = "github"
    authorize_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    userinfo_url = "https://api.github.com/user"
    emails_url = "https://api.github.com/user/emails"
    scopes = ["read:user", "user:email"]

    async def exchange_code(self, code: str) -> Optional[OAuthToken]:
        """Exchange code for GitHub token."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                    },
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"GitHub token exchange failed: {await resp.text()}")
                        return None

                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"GitHub token error: {data}")
                        return None

                    return OAuthToken(
                        access_token=data["access_token"],
                        token_type=data.get("token_type", "Bearer"),
                        scope=data.get("scope"),
                    )
        except Exception as e:
            logger.error(f"GitHub token exchange error: {e}")
            return None

    async def get_user_info(self, token: OAuthToken) -> Optional[OAuthUserInfo]:
        """Get user info from GitHub."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                # Get user profile
                async with session.get(
                    self.userinfo_url,
                    headers={
                        "Authorization": f"token {token.access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"GitHub userinfo failed: {await resp.text()}")
                        return None

                    user_data = await resp.json()

                # Get primary email
                email = user_data.get("email")
                email_verified = False

                if not email:
                    async with session.get(
                        self.emails_url,
                        headers={
                            "Authorization": f"token {token.access_token}",
                            "Accept": "application/vnd.github.v3+json",
                        },
                    ) as email_resp:
                        if email_resp.status == 200:
                            emails = await email_resp.json()
                            for e in emails:
                                if e.get("primary"):
                                    email = e.get("email")
                                    email_verified = e.get("verified", False)
                                    break

                if not email:
                    logger.error("GitHub: No email found")
                    return None

                return OAuthUserInfo(
                    provider="github",
                    provider_id=str(user_data["id"]),
                    email=email,
                    name=user_data.get("name") or user_data.get("login", ""),
                    avatar_url=user_data.get("avatar_url"),
                    email_verified=email_verified,
                )
        except Exception as e:
            logger.error(f"GitHub userinfo error: {e}")
            return None


class OAuthService:
    """OAuth service for managing social login."""

    def __init__(self, config: Optional[AuthConfig] = None):
        self.config = config or DEFAULT_AUTH_CONFIG
        self._providers: dict[str, OAuthProvider] = {}
        self._states: dict[str, dict] = {}  # In-memory state storage

        # Initialize providers if configured
        self._init_providers()

    def _init_providers(self):
        """Initialize OAuth providers from config."""
        if self.config.google_client_id and self.config.google_client_secret:
            self._providers["google"] = GoogleOAuthProvider(
                client_id=self.config.google_client_id,
                client_secret=self.config.google_client_secret,
                redirect_uri="http://localhost:8501/auth/callback/google",
            )

        if self.config.github_client_id and self.config.github_client_secret:
            self._providers["github"] = GitHubOAuthProvider(
                client_id=self.config.github_client_id,
                client_secret=self.config.github_client_secret,
                redirect_uri="http://localhost:8501/auth/callback/github",
            )

    def get_available_providers(self) -> list[str]:
        """Get list of configured providers."""
        return list(self._providers.keys())

    def generate_state(self, provider: str) -> str:
        """Generate and store OAuth state token."""
        state = secrets.token_urlsafe(32)
        self._states[state] = {
            "provider": provider,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=10),
        }
        return state

    def validate_state(self, state: str) -> Optional[str]:
        """Validate state and return provider name."""
        state_data = self._states.get(state)
        if not state_data:
            return None

        if datetime.utcnow() > state_data["expires_at"]:
            del self._states[state]
            return None

        provider = state_data["provider"]
        del self._states[state]  # One-time use
        return provider

    def get_authorize_url(self, provider: str) -> Optional[Tuple[str, str]]:
        """Get authorization URL for provider.

        Returns:
            Tuple of (url, state) or None if provider not available.
        """
        if provider not in self._providers:
            return None

        state = self.generate_state(provider)
        url = self._providers[provider].get_authorize_url(state)
        return url, state

    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str,
    ) -> Tuple[Optional[OAuthUserInfo], Optional[str]]:
        """Handle OAuth callback.

        Args:
            provider: Provider name.
            code: Authorization code.
            state: State token.

        Returns:
            Tuple of (user_info, error_message).
        """
        # Validate state
        validated_provider = self.validate_state(state)
        if validated_provider != provider:
            return None, "Invalid state token"

        oauth_provider = self._providers.get(provider)
        if not oauth_provider:
            return None, f"Provider {provider} not configured"

        # Exchange code for token
        token = await oauth_provider.exchange_code(code)
        if not token:
            return None, "Failed to exchange code for token"

        # Get user info
        user_info = await oauth_provider.get_user_info(token)
        if not user_info:
            return None, "Failed to get user info"

        return user_info, None


# Rate limiter for authentication endpoints
class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, requests: int = 100, window_seconds: int = 60):
        self.requests = requests
        self.window = timedelta(seconds=window_seconds)
        self._records: dict[str, list[datetime]] = {}

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed.

        Args:
            key: Rate limit key (e.g., IP address, user ID).

        Returns:
            True if request is allowed.
        """
        now = datetime.utcnow()
        window_start = now - self.window

        # Clean old records
        if key in self._records:
            self._records[key] = [t for t in self._records[key] if t > window_start]
        else:
            self._records[key] = []

        # Check limit
        if len(self._records[key]) >= self.requests:
            return False

        # Record request
        self._records[key].append(now)
        return True

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for key."""
        now = datetime.utcnow()
        window_start = now - self.window

        if key in self._records:
            valid_requests = [t for t in self._records[key] if t > window_start]
            return max(0, self.requests - len(valid_requests))

        return self.requests

    def get_reset_time(self, key: str) -> Optional[datetime]:
        """Get when rate limit resets."""
        if key not in self._records or not self._records[key]:
            return None

        oldest = min(self._records[key])
        return oldest + self.window


# Default rate limiter for auth endpoints
auth_rate_limiter = RateLimiter(requests=10, window_seconds=60)  # 10 login attempts per minute
api_rate_limiter = RateLimiter(requests=100, window_seconds=60)  # 100 API requests per minute
