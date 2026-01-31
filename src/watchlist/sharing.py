"""Watchlist Sharing.

Sharing and collaboration features for watchlists.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging
import secrets

from src.watchlist.config import Permission
from src.watchlist.models import WatchlistShare, Watchlist

logger = logging.getLogger(__name__)


class SharingManager:
    """Manages watchlist sharing and collaboration.
    
    Handles sharing permissions, link generation, and access control.
    
    Example:
        manager = SharingManager()
        
        # Share with specific user
        share = manager.share_with_user(
            watchlist_id="wl1",
            user_id="user123",
            permission=Permission.VIEW,
        )
        
        # Create public link
        link = manager.create_share_link(
            watchlist_id="wl1",
            expires_in_days=7,
        )
    """
    
    def __init__(self):
        self._shares: dict[str, WatchlistShare] = {}
        self._links: dict[str, str] = {}  # link -> share_id
    
    def share_with_user(
        self,
        watchlist_id: str,
        user_id: str,
        permission: Permission = Permission.VIEW,
        shared_by: str = "owner",
    ) -> WatchlistShare:
        """Share a watchlist with a specific user.
        
        Args:
            watchlist_id: Watchlist to share.
            user_id: User to share with.
            permission: Access permission level.
            shared_by: User initiating the share.
            
        Returns:
            Created WatchlistShare.
        """
        # Check for existing share
        existing = self.get_share_for_user(watchlist_id, user_id)
        if existing:
            existing.permission = permission
            return existing
        
        share = WatchlistShare(
            watchlist_id=watchlist_id,
            shared_with=user_id,
            permission=permission,
            shared_by=shared_by,
        )
        
        self._shares[share.share_id] = share
        return share
    
    def create_share_link(
        self,
        watchlist_id: str,
        permission: Permission = Permission.VIEW,
        expires_in_days: Optional[int] = None,
        shared_by: str = "owner",
    ) -> WatchlistShare:
        """Create a shareable link for a watchlist.
        
        Args:
            watchlist_id: Watchlist to share.
            permission: Access permission for link users.
            expires_in_days: Optional expiration (None = never).
            shared_by: User creating the link.
            
        Returns:
            WatchlistShare with share_link.
        """
        # Generate unique link
        link_token = secrets.token_urlsafe(16)
        
        # Calculate expiration
        expires = None
        if expires_in_days:
            expires = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        
        share = WatchlistShare(
            watchlist_id=watchlist_id,
            shared_with="public",
            permission=permission,
            shared_by=shared_by,
            share_link=link_token,
            link_expires=expires,
        )
        
        self._shares[share.share_id] = share
        self._links[link_token] = share.share_id
        return share
    
    def get_share(self, share_id: str) -> Optional[WatchlistShare]:
        """Get share by ID."""
        return self._shares.get(share_id)
    
    def get_share_by_link(self, link_token: str) -> Optional[WatchlistShare]:
        """Get share by link token."""
        share_id = self._links.get(link_token)
        if share_id:
            share = self._shares.get(share_id)
            if share and share.is_link_valid:
                return share
        return None
    
    def get_share_for_user(
        self,
        watchlist_id: str,
        user_id: str,
    ) -> Optional[WatchlistShare]:
        """Get share for a specific user."""
        for share in self._shares.values():
            if share.watchlist_id == watchlist_id and share.shared_with == user_id:
                return share
        return None
    
    def get_shares_for_watchlist(self, watchlist_id: str) -> list[WatchlistShare]:
        """Get all shares for a watchlist."""
        return [s for s in self._shares.values() if s.watchlist_id == watchlist_id]
    
    def get_watchlists_shared_with_user(self, user_id: str) -> list[str]:
        """Get watchlist IDs shared with a user.
        
        Returns:
            List of watchlist IDs.
        """
        return [
            s.watchlist_id for s in self._shares.values()
            if s.shared_with == user_id
        ]
    
    def update_permission(
        self,
        share_id: str,
        permission: Permission,
    ) -> Optional[WatchlistShare]:
        """Update share permission."""
        share = self._shares.get(share_id)
        if share:
            share.permission = permission
            return share
        return None
    
    def revoke_share(self, share_id: str) -> bool:
        """Revoke a share."""
        share = self._shares.get(share_id)
        if share:
            # Remove link if exists
            if share.share_link and share.share_link in self._links:
                del self._links[share.share_link]
            
            del self._shares[share_id]
            return True
        return False
    
    def revoke_link(self, link_token: str) -> bool:
        """Revoke a share link."""
        share_id = self._links.get(link_token)
        if share_id:
            share = self._shares.get(share_id)
            if share:
                share.share_link = None
                share.link_expires = None
            del self._links[link_token]
            return True
        return False
    
    def check_access(
        self,
        watchlist_id: str,
        user_id: str,
        required_permission: Permission = Permission.VIEW,
    ) -> bool:
        """Check if user has required access to watchlist.
        
        Args:
            watchlist_id: Watchlist to check.
            user_id: User requesting access.
            required_permission: Minimum permission needed.
            
        Returns:
            True if user has access.
        """
        share = self.get_share_for_user(watchlist_id, user_id)
        if not share:
            return False
        
        # Permission hierarchy: VIEW < EDIT < ADMIN
        permission_levels = {
            Permission.VIEW: 1,
            Permission.EDIT: 2,
            Permission.ADMIN: 3,
        }
        
        return permission_levels[share.permission] >= permission_levels[required_permission]
    
    def make_public(self, watchlist_id: str, shared_by: str = "owner") -> WatchlistShare:
        """Make a watchlist public (anyone can view).
        
        Returns:
            Public share.
        """
        # Check for existing public share
        for share in self._shares.values():
            if share.watchlist_id == watchlist_id and share.shared_with == "public":
                return share
        
        return self.share_with_user(
            watchlist_id=watchlist_id,
            user_id="public",
            permission=Permission.VIEW,
            shared_by=shared_by,
        )
    
    def make_private(self, watchlist_id: str) -> bool:
        """Make a watchlist private (revoke all shares).
        
        Returns:
            True if any shares were revoked.
        """
        shares = self.get_shares_for_watchlist(watchlist_id)
        if not shares:
            return False
        
        for share in shares:
            self.revoke_share(share.share_id)
        
        return True
    
    def get_share_stats(self, watchlist_id: str) -> dict:
        """Get sharing statistics for a watchlist.
        
        Returns:
            Dict with sharing stats.
        """
        shares = self.get_shares_for_watchlist(watchlist_id)
        
        return {
            "total_shares": len(shares),
            "user_shares": len([s for s in shares if s.shared_with != "public"]),
            "public_links": len([s for s in shares if s.share_link]),
            "view_only": len([s for s in shares if s.permission == Permission.VIEW]),
            "can_edit": len([s for s in shares if s.permission in [Permission.EDIT, Permission.ADMIN]]),
        }
