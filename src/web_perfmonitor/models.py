"""Data models for web-perfmonitor.

This module defines the core data structures used throughout the package,
including PerformanceProfile, AlertRecord, TaskStatus, and NotificationTask.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class PerformanceProfile:
    """Represents a single performance profiling result.

    This immutable dataclass captures all information about a profiled
    request or function execution.

    Attributes:
        id: Unique identifier (UUID) for this profile.
        endpoint: The endpoint path (middleware mode) or function name (decorator mode).
        method: HTTP method (middleware mode) or "FUNCTION" (decorator mode).
        duration_seconds: Execution time in seconds.
        timestamp: When the profiling occurred.
        html_report: Pyinstrument HTML format report.
        text_report: Pyinstrument text format report.
        metadata: Additional context information including:
            - url: Full request URL
            - path: Request path
            - method: HTTP method
            - remote_addr: Client IP address
            - user_agent: User agent string
            - query_params: URL query parameters dict
            - form_data: Form data dict
            - json_body: JSON request body
            - request_headers: HTTP request headers dict (if enabled)
    """

    id: str
    endpoint: str
    method: str
    duration_seconds: float
    timestamp: datetime
    html_report: str
    text_report: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        endpoint: str,
        method: str,
        duration_seconds: float,
        html_report: str,
        text_report: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "PerformanceProfile":
        """Factory method to create a new PerformanceProfile.

        Args:
            endpoint: The endpoint path or function name.
            method: HTTP method or "FUNCTION".
            duration_seconds: Execution time in seconds.
            html_report: Pyinstrument HTML report.
            text_report: Pyinstrument text report.
            metadata: Optional additional context.

        Returns:
            A new PerformanceProfile instance.
        """
        return cls(
            id=str(uuid4()),
            endpoint=endpoint,
            method=method,
            duration_seconds=duration_seconds,
            timestamp=datetime.now(),
            html_report=html_report,
            text_report=text_report,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with all profile data.
        """
        return {
            "id": self.id,
            "endpoint": self.endpoint,
            "method": self.method,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp.isoformat(),
            "html_report": self.html_report,
            "text_report": self.text_report,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            JSON string representation.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class AlertRecord:
    """Record for alert deduplication.

    Tracks when alerts were sent for each endpoint to prevent
    duplicate notifications within the configured time window.

    Attributes:
        endpoint: The endpoint path or function name (primary key).
        last_alert_time: When the last alert was sent.
        alert_count: Total number of alerts sent for this endpoint.
    """

    endpoint: str
    last_alert_time: datetime
    alert_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with alert record data.
        """
        return {
            "endpoint": self.endpoint,
            "last_alert_time": self.last_alert_time.isoformat(),
            "alert_count": self.alert_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertRecord":
        """Create from dictionary representation.

        Args:
            data: Dictionary with alert record data.

        Returns:
            AlertRecord instance.
        """
        return cls(
            endpoint=data["endpoint"],
            last_alert_time=datetime.fromisoformat(data["last_alert_time"]),
            alert_count=data.get("alert_count", 1),
        )


class TaskStatus(Enum):
    """Status of a notification task.

    Values:
        PENDING: Task is waiting to be executed.
        RUNNING: Task is currently executing.
        COMPLETED: Task finished (may have partial failures).
        FAILED: All notification attempts failed.
        TIMEOUT: Task was abandoned due to timeout.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class NotificationTask:
    """Represents an async notification task.

    Encapsulates all information needed to send notifications
    about a performance alert.

    Attributes:
        id: Unique task identifier.
        profile: The PerformanceProfile that triggered this notification.
        notifier_configs: List of notification channel configurations.
        created_at: When the task was created.
        status: Current task status.
        errors: List of error messages from failed notification attempts.
    """

    id: str
    profile: PerformanceProfile
    notifier_configs: List[Dict[str, Any]]
    created_at: datetime
    status: TaskStatus = TaskStatus.PENDING
    errors: List[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        profile: PerformanceProfile,
        notifier_configs: List[Dict[str, Any]],
    ) -> "NotificationTask":
        """Factory method to create a new NotificationTask.

        Args:
            profile: The PerformanceProfile to notify about.
            notifier_configs: List of notification channel configurations.

        Returns:
            A new NotificationTask instance.
        """
        return cls(
            id=str(uuid4()),
            profile=profile,
            notifier_configs=notifier_configs,
            created_at=datetime.now(),
        )

    def mark_running(self) -> None:
        """Mark the task as running."""
        self.status = TaskStatus.RUNNING

    def mark_completed(self, errors: Optional[List[str]] = None) -> None:
        """Mark the task as completed.

        Args:
            errors: Optional list of error messages from partial failures.
        """
        self.status = TaskStatus.COMPLETED
        if errors:
            self.errors.extend(errors)

    def mark_failed(self, errors: List[str]) -> None:
        """Mark the task as failed.

        Args:
            errors: List of error messages.
        """
        self.status = TaskStatus.FAILED
        self.errors.extend(errors)

    def mark_timeout(self) -> None:
        """Mark the task as timed out."""
        self.status = TaskStatus.TIMEOUT
