"""Alert management for deduplication.

This module provides the AlertManager class for tracking alerts
and implementing time-window based deduplication.
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from .models import AlertRecord

if TYPE_CHECKING:
    from .config import MonitorConfig

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert deduplication based on time windows.

    Tracks when alerts were last sent for each endpoint and suppresses
    duplicate alerts within the configured time window.

    Alerts are persisted to a JSON file to survive restarts.

    Attributes:
        config: The monitoring configuration.
        alert_window: Time window for deduplication.
        alerts_file: Path to the alerts persistence file.

    Example:
        manager = AlertManager(config)

        # Check if we should send an alert
        if manager.should_alert("/api/users"):
            # Record that we're sending an alert
            manager.record_alert("/api/users")
            send_notification(profile)
    """

    def __init__(self, config: "MonitorConfig") -> None:
        """Initialize the alert manager.

        Args:
            config: The monitoring configuration.
        """
        self.config = config
        self.alert_window = timedelta(days=config.alert_window_days)
        self.alerts_file = Path(config.log_path) / "alerts.json"
        self._alerts: Dict[str, AlertRecord] = {}
        self._lock = threading.Lock()
        self._load_alerts()

    def should_alert(self, endpoint: str) -> bool:
        """Check if an alert should be sent for the given endpoint.

        Returns True if no alert has been sent for this endpoint within
        the configured time window.

        Args:
            endpoint: The endpoint identifier (e.g., "/api/users").

        Returns:
            True if an alert should be sent, False if suppressed.
        """
        with self._lock:
            record = self._alerts.get(endpoint)
            if record is None:
                return True

            # Check if the record has expired
            now = datetime.utcnow()
            if now - record.last_alert_time > self.alert_window:
                return True

            return False

    def record_alert(self, endpoint: str) -> None:
        """Record that an alert was sent for the given endpoint.

        Updates the alert record and persists to disk.

        Args:
            endpoint: The endpoint identifier.
        """
        with self._lock:
            now = datetime.utcnow()
            record = self._alerts.get(endpoint)

            if record is None:
                self._alerts[endpoint] = AlertRecord(
                    endpoint=endpoint,
                    last_alert_time=now,
                    alert_count=1,
                )
            else:
                self._alerts[endpoint] = AlertRecord(
                    endpoint=endpoint,
                    last_alert_time=now,
                    alert_count=record.alert_count + 1,
                )

            self._save_alerts()

    def get_alert_record(self, endpoint: str) -> Optional[AlertRecord]:
        """Get the alert record for an endpoint.

        Args:
            endpoint: The endpoint identifier.

        Returns:
            The AlertRecord if exists, None otherwise.
        """
        with self._lock:
            return self._alerts.get(endpoint)

    def clear_alert(self, endpoint: str) -> bool:
        """Clear the alert record for an endpoint.

        Args:
            endpoint: The endpoint identifier.

        Returns:
            True if a record was cleared, False if not found.
        """
        with self._lock:
            if endpoint in self._alerts:
                del self._alerts[endpoint]
                self._save_alerts()
                return True
            return False

    def clear_all(self) -> int:
        """Clear all alert records.

        Returns:
            Number of records cleared.
        """
        with self._lock:
            count = len(self._alerts)
            self._alerts.clear()
            self._save_alerts()
            return count

    def cleanup_expired(self) -> int:
        """Remove expired alert records.

        Returns:
            Number of records removed.
        """
        with self._lock:
            now = datetime.utcnow()
            expired = [
                endpoint
                for endpoint, record in self._alerts.items()
                if now - record.last_alert_time > self.alert_window
            ]

            for endpoint in expired:
                del self._alerts[endpoint]

            if expired:
                self._save_alerts()

            return len(expired)

    def _load_alerts(self) -> None:
        """Load alerts from the persistence file.

        Handles missing or corrupted files gracefully.
        """
        if not self.alerts_file.exists():
            logger.debug(f"No alerts file found at {self.alerts_file}")
            return

        try:
            data = json.loads(self.alerts_file.read_text(encoding="utf-8"))

            for endpoint, record_data in data.items():
                try:
                    self._alerts[endpoint] = AlertRecord(
                        endpoint=endpoint,
                        last_alert_time=datetime.fromisoformat(record_data["last_alert"]),
                        alert_count=record_data.get("alert_count", 1),
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping invalid alert record for {endpoint}: {e}")

            logger.debug(f"Loaded {len(self._alerts)} alert records from {self.alerts_file}")

        except json.JSONDecodeError as e:
            logger.warning(
                f"Corrupted alerts file at {self.alerts_file}, resetting: {e}"
            )
            self._alerts.clear()
            self._save_alerts()
        except Exception as e:
            logger.error(f"Error loading alerts file: {e}", exc_info=True)

    def _save_alerts(self) -> None:
        """Save alerts to the persistence file.

        Creates the directory if it doesn't exist.
        """
        try:
            # Ensure directory exists
            self.alerts_file.parent.mkdir(parents=True, exist_ok=True)

            # Serialize alerts
            data = {
                endpoint: {
                    "last_alert": record.last_alert_time.isoformat(),
                    "alert_count": record.alert_count,
                }
                for endpoint, record in self._alerts.items()
            }

            # Write atomically (write to temp, then rename)
            temp_file = self.alerts_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_file.rename(self.alerts_file)

            logger.debug(f"Saved {len(self._alerts)} alert records to {self.alerts_file}")

        except Exception as e:
            logger.error(f"Error saving alerts file: {e}", exc_info=True)
