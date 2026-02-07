"""Device registration and management."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict

from src.notifications.config import Platform, TokenType, NotificationConfig, DEFAULT_NOTIFICATION_CONFIG
from src.notifications.models import Device


class DeviceManager:
    """Manages device registrations for push notifications."""

    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or DEFAULT_NOTIFICATION_CONFIG
        self._devices: dict[str, Device] = {}  # device_id -> Device
        self._user_devices: dict[str, list[str]] = defaultdict(list)  # user_id -> [device_ids]
        self._token_to_device: dict[str, str] = {}  # device_token -> device_id

    def register_device(
        self,
        user_id: str,
        device_token: str,
        platform: Platform,
        token_type: Optional[TokenType] = None,
        device_name: Optional[str] = None,
        device_model: Optional[str] = None,
        app_version: Optional[str] = None,
        os_version: Optional[str] = None,
    ) -> Device:
        """Register a new device or update existing one."""
        # Auto-detect token type based on platform if not provided
        if token_type is None:
            token_type = self._detect_token_type(platform)

        # Check if token already registered
        if device_token in self._token_to_device:
            existing_id = self._token_to_device[device_token]
            existing = self._devices.get(existing_id)
            if existing:
                # Update existing device
                existing.user_id = user_id
                existing.device_name = device_name or existing.device_name
                existing.device_model = device_model or existing.device_model
                existing.app_version = app_version or existing.app_version
                existing.os_version = os_version or existing.os_version
                existing.is_active = True
                existing.mark_used()
                return existing

        # Create new device
        device = Device(
            user_id=user_id,
            device_token=device_token,
            platform=platform,
            token_type=token_type,
            device_name=device_name,
            device_model=device_model,
            app_version=app_version,
            os_version=os_version,
        )

        self._devices[device.device_id] = device
        self._user_devices[user_id].append(device.device_id)
        self._token_to_device[device_token] = device.device_id

        return device

    def _detect_token_type(self, platform: Platform) -> TokenType:
        """Detect token type based on platform."""
        if platform == Platform.IOS:
            return TokenType.APNS
        elif platform == Platform.ANDROID:
            return TokenType.FCM
        else:
            return TokenType.WEB_PUSH

    def get_device(self, device_id: str) -> Optional[Device]:
        """Get device by ID."""
        return self._devices.get(device_id)

    def get_device_by_token(self, device_token: str) -> Optional[Device]:
        """Get device by token."""
        device_id = self._token_to_device.get(device_token)
        if device_id:
            return self._devices.get(device_id)
        return None

    def get_user_devices(self, user_id: str, active_only: bool = True) -> list[Device]:
        """Get all devices for a user."""
        device_ids = self._user_devices.get(user_id, [])
        devices = [self._devices[did] for did in device_ids if did in self._devices]

        if active_only:
            devices = [d for d in devices if d.is_active]

        return devices

    def unregister_device(self, device_id: str) -> bool:
        """Unregister a device."""
        device = self._devices.get(device_id)
        if not device:
            return False

        # Remove from all indexes
        del self._devices[device_id]

        if device.device_token in self._token_to_device:
            del self._token_to_device[device.device_token]

        user_devices = self._user_devices.get(device.user_id, [])
        if device_id in user_devices:
            user_devices.remove(device_id)

        return True

    def deactivate_device(self, device_id: str) -> bool:
        """Deactivate a device (keeps record but won't receive notifications)."""
        device = self._devices.get(device_id)
        if not device:
            return False

        device.deactivate()
        return True

    def refresh_token(self, device_id: str, new_token: str) -> bool:
        """Refresh a device's push token."""
        device = self._devices.get(device_id)
        if not device:
            return False

        old_token = device.device_token

        # Remove old token mapping
        if old_token in self._token_to_device:
            del self._token_to_device[old_token]

        # Update device and add new mapping
        device.refresh_token(new_token)
        self._token_to_device[new_token] = device_id

        return True

    def mark_device_used(self, device_id: str) -> bool:
        """Mark device as recently used."""
        device = self._devices.get(device_id)
        if not device:
            return False

        device.mark_used()
        return True

    def mark_token_invalid(self, device_token: str) -> bool:
        """Mark a token as invalid (deactivate device)."""
        device = self.get_device_by_token(device_token)
        if not device:
            return False

        device.deactivate()
        return True

    def get_stale_devices(self, days: int = 90) -> list[Device]:
        """Get devices that haven't been used recently."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stale = []

        for device in self._devices.values():
            last_used = device.last_used_at or device.created_at
            if last_used < cutoff:
                stale.append(device)

        return stale

    def cleanup_stale_devices(self, days: int = 90) -> int:
        """Remove stale devices."""
        stale = self.get_stale_devices(days)
        count = 0

        for device in stale:
            if self.unregister_device(device.device_id):
                count += 1

        return count

    def get_device_count(self, user_id: Optional[str] = None) -> int:
        """Get device count."""
        if user_id:
            return len(self.get_user_devices(user_id))
        return len(self._devices)

    def get_platform_breakdown(self) -> dict[str, int]:
        """Get device count by platform."""
        breakdown: dict[str, int] = {}
        for device in self._devices.values():
            if device.is_active:
                platform = device.platform.value
                breakdown[platform] = breakdown.get(platform, 0) + 1
        return breakdown

    def get_stats(self) -> dict:
        """Get device registration statistics."""
        total = len(self._devices)
        active = sum(1 for d in self._devices.values() if d.is_active)

        return {
            "total_devices": total,
            "active_devices": active,
            "inactive_devices": total - active,
            "unique_users": len(self._user_devices),
            "by_platform": self.get_platform_breakdown(),
        }
