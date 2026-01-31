"""Credential and Token Management.

Secure storage and management of broker credentials and OAuth tokens.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
import base64
import hashlib
import json
import logging
import os
import secrets

from src.brokers.config import BrokerType, AuthMethod

logger = logging.getLogger(__name__)


@dataclass
class BrokerCredentials:
    """Broker authentication credentials."""
    credential_id: str = ""
    broker: BrokerType = BrokerType.ALPACA
    account_id: str = ""
    
    # OAuth tokens
    access_token: str = ""
    refresh_token: str = ""
    token_expiry: Optional[datetime] = None
    token_type: str = "Bearer"
    
    # API keys (for brokers that use them)
    api_key: str = ""
    api_secret: str = ""
    
    # State
    is_valid: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.token_expiry is None:
            return False
        # Consider expired 5 minutes before actual expiry
        buffer = timedelta(minutes=5)
        return datetime.now(timezone.utc) >= (self.token_expiry - buffer)
    
    @property
    def expires_in_seconds(self) -> int:
        """Get seconds until token expires."""
        if self.token_expiry is None:
            return -1
        delta = self.token_expiry - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))


class CredentialManager:
    """Manages broker credentials securely.
    
    Features:
    - Secure storage with encryption
    - Token refresh tracking
    - Multiple account support
    
    Example:
        manager = CredentialManager()
        manager.store_credentials(credentials)
        creds = manager.get_credentials("alpaca", "account123")
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """Initialize credential manager.
        
        Args:
            encryption_key: Key for encrypting credentials.
                           If not provided, uses environment variable.
        """
        self._encryption_key = encryption_key or os.environ.get(
            "BROKER_ENCRYPTION_KEY",
            self._generate_key()
        )
        self._credentials: dict[str, BrokerCredentials] = {}
    
    def _generate_key(self) -> str:
        """Generate a random encryption key."""
        return secrets.token_hex(32)
    
    def _get_credential_key(self, broker: BrokerType, account_id: str) -> str:
        """Get unique key for credential lookup."""
        return f"{broker.value}:{account_id}"
    
    def store_credentials(self, credentials: BrokerCredentials) -> str:
        """Store credentials securely.
        
        Args:
            credentials: Credentials to store.
            
        Returns:
            Credential ID.
        """
        if not credentials.credential_id:
            credentials.credential_id = secrets.token_hex(8)
        
        key = self._get_credential_key(credentials.broker, credentials.account_id)
        credentials.updated_at = datetime.now(timezone.utc)
        
        # In production, would encrypt before storing
        self._credentials[key] = credentials
        
        logger.info(f"Stored credentials for {key}")
        return credentials.credential_id
    
    def get_credentials(
        self,
        broker: BrokerType,
        account_id: str,
    ) -> Optional[BrokerCredentials]:
        """Get credentials for a broker account.
        
        Args:
            broker: Broker type.
            account_id: Account ID.
            
        Returns:
            Credentials if found, None otherwise.
        """
        key = self._get_credential_key(broker, account_id)
        return self._credentials.get(key)
    
    def update_tokens(
        self,
        broker: BrokerType,
        account_id: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> bool:
        """Update OAuth tokens.
        
        Args:
            broker: Broker type.
            account_id: Account ID.
            access_token: New access token.
            refresh_token: New refresh token (optional).
            expires_in: Token lifetime in seconds.
            
        Returns:
            True if updated successfully.
        """
        creds = self.get_credentials(broker, account_id)
        if not creds:
            return False
        
        creds.access_token = access_token
        if refresh_token:
            creds.refresh_token = refresh_token
        
        if expires_in:
            creds.token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        creds.updated_at = datetime.now(timezone.utc)
        
        key = self._get_credential_key(broker, account_id)
        self._credentials[key] = creds
        
        return True
    
    def delete_credentials(self, broker: BrokerType, account_id: str) -> bool:
        """Delete credentials.
        
        Args:
            broker: Broker type.
            account_id: Account ID.
            
        Returns:
            True if deleted, False if not found.
        """
        key = self._get_credential_key(broker, account_id)
        if key in self._credentials:
            del self._credentials[key]
            logger.info(f"Deleted credentials for {key}")
            return True
        return False
    
    def get_all_credentials(self) -> list[BrokerCredentials]:
        """Get all stored credentials."""
        return list(self._credentials.values())
    
    def get_credentials_by_broker(self, broker: BrokerType) -> list[BrokerCredentials]:
        """Get all credentials for a specific broker."""
        return [c for c in self._credentials.values() if c.broker == broker]
    
    def is_token_valid(self, broker: BrokerType, account_id: str) -> bool:
        """Check if credentials are valid and not expired.
        
        Args:
            broker: Broker type.
            account_id: Account ID.
            
        Returns:
            True if valid and not expired.
        """
        creds = self.get_credentials(broker, account_id)
        if not creds:
            return False
        return creds.is_valid and not creds.is_expired


class OAuthManager:
    """Manages OAuth authentication flows.
    
    Example:
        oauth = OAuthManager(config)
        url = oauth.get_authorization_url()
        tokens = await oauth.exchange_code(code)
    """
    
    def __init__(
        self,
        broker: BrokerType,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ):
        self.broker = broker
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._state: Optional[str] = None
    
    def get_authorization_url(self, scope: str = "") -> str:
        """Get OAuth authorization URL.
        
        Args:
            scope: OAuth scope.
            
        Returns:
            Authorization URL to redirect user to.
        """
        from src.brokers.config import OAUTH_ENDPOINTS
        
        endpoints = OAUTH_ENDPOINTS.get(self.broker, {})
        auth_url = endpoints.get("authorize", "")
        default_scope = endpoints.get("scope", "")
        
        self._state = secrets.token_urlsafe(32)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope or default_scope,
            "state": self._state,
        }
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{auth_url}?{query}"
    
    async def exchange_code(
        self,
        code: str,
        state: Optional[str] = None,
    ) -> Optional[dict]:
        """Exchange authorization code for tokens.
        
        Args:
            code: Authorization code.
            state: State parameter for verification.
            
        Returns:
            Token response dict or None on failure.
        """
        # Verify state
        if state and self._state and state != self._state:
            logger.error("OAuth state mismatch")
            return None
        
        from src.brokers.config import OAUTH_ENDPOINTS
        
        endpoints = OAUTH_ENDPOINTS.get(self.broker, {})
        token_url = endpoints.get("token", "")
        
        # In production, would make actual HTTP request
        # This is a placeholder implementation
        logger.info(f"Would exchange code at {token_url}")
        
        # Simulated response
        return {
            "access_token": f"simulated_access_{secrets.token_hex(16)}",
            "refresh_token": f"simulated_refresh_{secrets.token_hex(16)}",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    
    async def refresh_tokens(
        self,
        refresh_token: str,
    ) -> Optional[dict]:
        """Refresh OAuth tokens.
        
        Args:
            refresh_token: Refresh token.
            
        Returns:
            New token response dict or None on failure.
        """
        from src.brokers.config import OAUTH_ENDPOINTS
        
        endpoints = OAUTH_ENDPOINTS.get(self.broker, {})
        token_url = endpoints.get("token", "")
        
        logger.info(f"Would refresh token at {token_url}")
        
        # Simulated response
        return {
            "access_token": f"refreshed_access_{secrets.token_hex(16)}",
            "refresh_token": f"refreshed_refresh_{secrets.token_hex(16)}",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
