"""Alert management for deduplication.

This module provides the AlertManager class for tracking alerts
and implementing time-window based deduplication.
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from .models import AlertRecord

if TYPE_CHECKING:
    from .config import MonitorConfig

logger = logging.getLogger(__name__)

# Default maximum number of alert records to prevent unbounded memory growth
DEFAULT_MAX_ALERT_RECORDS = 10000
# Default cleanup interval in seconds (1 hour)
DEFAULT_CLEANUP_INTERVAL = 3600


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

    def __init__(
        self,
        config: "MonitorConfig",
        max_records: int = DEFAULT_MAX_ALERT_RECORDS,
        auto_cleanup: bool = True,
        cleanup_interval: int = DEFAULT_CLEANUP_INTERVAL,
    ) -> None:
        """Initialize the alert manager.

        Args:
            config: The monitoring configuration.
            max_records: Maximum number of alert records to keep in memory.
            auto_cleanup: Whether to start automatic cleanup thread.
            cleanup_interval: Interval between automatic cleanups (seconds).
        """
        self.config = config
        self.alert_window = timedelta(days=config.alert_window_days)
        self.alerts_file = Path(config.log_path) / "alerts.json"
        self._alerts: Dict[str, AlertRecord] = {}
        self._lock = threading.Lock()
        self._max_records = max_records
        self._cleanup_interval = cleanup_interval
        self._shutdown = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._load_alerts()

        # Start automatic cleanup thread if enabled
        if auto_cleanup:
            self._start_cleanup_thread()

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
        Enforces max_records limit by evicting oldest entries.

        Args:
            endpoint: The endpoint identifier.
        """
        with self._lock:
            now = datetime.utcnow()
            record = self._alerts.get(endpoint)

            if record is None:
                # Check if we need to evict old records before adding new one
                self._evict_if_needed()
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

            # Write atomically (write to temp, then replace)
            # Use replace() instead of rename() for Windows compatibility
            # rename() fails on Windows if target file exists
            temp_file = self.alerts_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_file.replace(self.alerts_file)

            logger.debug(f"Saved {len(self._alerts)} alert records to {self.alerts_file}")

        except Exception as e:
            logger.error(f"Error saving alerts file: {e}", exc_info=True)

    def _evict_if_needed(self) -> int:
        """Evict oldest records if we're at max capacity.

        Must be called with lock held.

        Returns:
            Number of records evicted.
        """
        if len(self._alerts) < self._max_records:
            return 0

        # Evict 10% of oldest records to avoid frequent evictions
        evict_count = max(1, self._max_records // 10)

        # Sort by last_alert_time and evict oldest
        sorted_endpoints = sorted(
            self._alerts.items(),
            key=lambda x: x[1].last_alert_time,
        )

        evicted = 0
        for endpoint, _ in sorted_endpoints[:evict_count]:
            del self._alerts[endpoint]
            evicted += 1

        if evicted > 0:
            logger.info(f"Evicted {evicted} oldest alert records (max={self._max_records})")

        return evicted

    def _start_cleanup_thread(self) -> None:
        """Start the background cleanup thread."""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="alert-cleanup",
            daemon=True,
        )
        self._cleanup_thread.start()
        logger.debug(f"Started alert cleanup thread (interval={self._cleanup_interval}s)")

    def _cleanup_loop(self) -> None:
        """Background loop for periodic cleanup."""
        while not self._shutdown:
            # Sleep in small intervals to allow quick shutdown
            for _ in range(self._cleanup_interval):
                if self._shutdown:
                    break
                time.sleep(1)

            if not self._shutdown:
                expired = self.cleanup_expired()
                if expired > 0:
                    logger.info(f"Automatic cleanup removed {expired} expired alert records")

    def shutdown(self) -> None:
        """Shutdown the alert manager and cleanup thread."""
        self._shutdown = True
        if self._cleanup_thread is not None and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2.0)
            logger.debug("Alert cleanup thread stopped")

    @property
    def record_count(self) -> int:
        """Get the current number of alert records.

        Returns:
            Number of records in memory.
        """
        with self._lock:
            return len(self._alerts)
