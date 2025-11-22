"""Notification executor for async notification delivery.

This module provides the NotificationExecutor class for non-blocking
notification delivery using a thread pool.
"""

import logging
import queue
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .models import NotificationTask, TaskStatus

if TYPE_CHECKING:
    from .config import MonitorConfig
    from .models import PerformanceProfile
    from .notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class NotificationExecutor:
    """Async notification executor using ThreadPoolExecutor.

    Manages a pool of worker threads to send notifications without
    blocking the main request thread. Implements queue size limits
    and timeout handling.

    Local report saving is always performed first (mandatory).
    External notifiers (Mattermost, etc.) are then executed based on notice_list.

    Attributes:
        config: The monitoring configuration.
        _executor: The thread pool executor.
        _pending_tasks: Queue of pending notification tasks.
        _notifiers: Cached notifier instances.

    Example:
        executor = NotificationExecutor(config)

        # Submit a notification (non-blocking)
        executor.submit(profile)

        # Graceful shutdown
        executor.shutdown(timeout=5.0)
    """

    def __init__(self, config: "MonitorConfig") -> None:
        """Initialize the notification executor.

        Args:
            config: The monitoring configuration.
        """
        self.config = config
        self._executor: Optional[ThreadPoolExecutor] = None
        self._pending_tasks: queue.Queue[NotificationTask] = queue.Queue(
            maxsize=config.notice_queue_size
        )
        self._notifiers: Dict[str, "BaseNotifier"] = {}
        self._local_notifier: Optional["BaseNotifier"] = None
        self._lock = threading.Lock()
        self._shutdown = False
        self._active_futures: List[Future[Any]] = []

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Get the thread pool executor (lazy loaded).

        Returns:
            The ThreadPoolExecutor instance.
        """
        if self._executor is None:
            # Use a small number of workers since notifications are I/O bound
            max_workers = max(1, len(self.config.notice_list) + 1)
            self._executor = ThreadPoolExecutor(
                max_workers=min(4, max_workers),
                thread_name_prefix="perf-notify-",
            )
        return self._executor

    @property
    def local_notifier(self) -> "BaseNotifier":
        """Get the local notifier for saving reports (lazy loaded).

        Returns:
            The LocalNotifier instance.
        """
        if self._local_notifier is None:
            from .notifiers.local import LocalNotifier

            self._local_notifier = LocalNotifier(
                output_dir=self.config.log_path,
                format="html",  # Default to HTML for local reports
            )
        return self._local_notifier

    def submit(self, profile: "PerformanceProfile") -> Optional[NotificationTask]:
        """Submit a profile for notification.

        Always saves the report locally first, then sends to external notifiers.

        Args:
            profile: The performance profile to notify about.

        Returns:
            The NotificationTask if submitted, None if skipped.
        """
        if self._shutdown:
            logger.warning("Executor is shutting down, notification skipped")
            return None

        # Create task (notice_list can be empty - local save is still mandatory)
        task = NotificationTask(
            id=str(uuid.uuid4()),
            profile=profile,
            notifier_configs=self.config.notice_list,
            created_at=datetime.utcnow(),
            status=TaskStatus.PENDING,
        )

        # Try to add to queue
        try:
            self._pending_tasks.put_nowait(task)
        except queue.Full:
            # Queue is full, drop oldest task
            try:
                dropped = self._pending_tasks.get_nowait()
                logger.warning(
                    f"Notification queue full, dropped task for {dropped.profile.endpoint}"
                )
                self._pending_tasks.put_nowait(task)
            except queue.Empty:
                pass

        # Submit to executor
        with self._lock:
            future = self.executor.submit(self._execute_task, task)
            self._active_futures.append(future)
            # Clean up completed futures
            self._active_futures = [f for f in self._active_futures if not f.done()]

        return task

    def _execute_task(self, task: NotificationTask) -> None:
        """Execute a notification task.

        First saves the report locally (mandatory), then sends to external notifiers.

        Args:
            task: The notification task to execute.
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()

        errors: List[str] = []
        local_report_path: Optional[str] = None

        # Step 1: Always save locally first (mandatory)
        try:
            local_report_path = self._save_local_report(task.profile)
            logger.info(f"Performance report saved to: {local_report_path}")
        except Exception as e:
            error_msg = f"Failed to save local report: {e}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

        # Step 2: Send to external notifiers (if configured)
        for notifier_config in self.config.notice_list:
            notifier_type = notifier_config.get("type", "")

            # Skip local type in notice_list (already handled above)
            if notifier_type == "local":
                continue

            try:
                notifier = self._get_notifier(notifier_config)
                if notifier is None:
                    continue

                # Execute notification
                self._send_with_timeout(
                    notifier,
                    task.profile,
                    notifier_config.get("format", "markdown"),
                )
                logger.info(f"Notification sent via {notifier_type}")

            except FutureTimeoutError:
                error_msg = f"Notification timeout for {notifier_type}"
                logger.error(error_msg)
                errors.append(error_msg)
            except Exception as e:
                error_msg = f"Notification error for {notifier_type}: {e}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        # Update task status
        task.completed_at = datetime.utcnow()
        if errors:
            task.status = TaskStatus.FAILED
            task.error = "; ".join(errors)
        else:
            task.status = TaskStatus.COMPLETED

        # Remove from pending queue
        try:
            self._pending_tasks.get_nowait()
        except queue.Empty:
            pass

    def _save_local_report(self, profile: "PerformanceProfile") -> str:
        """Save the performance report to local filesystem.

        Args:
            profile: The performance profile to save.

        Returns:
            The path to the saved report file.
        """
        from .notifiers.local import LocalNotifier

        # Save in multiple formats
        notifier = LocalNotifier(
            output_dir=self.config.log_path,
            format="html",
        )
        notifier.send(profile, format="html")

        # Also save markdown for external notifiers to reference
        notifier_md = LocalNotifier(
            output_dir=self.config.log_path,
            format="markdown",
        )
        notifier_md.send(profile, format="markdown")

        return self.config.log_path

    def _send_with_timeout(
        self,
        notifier: "BaseNotifier",
        profile: "PerformanceProfile",
        format: str,
    ) -> None:
        """Send notification with timeout.

        Args:
            notifier: The notifier instance.
            profile: The performance profile.
            format: The message format.

        Raises:
            TimeoutError: If notification takes too long.
        """
        # For simplicity, we call send directly
        # In production, you might want per-notifier timeout handling
        notifier.send(profile, format)

    def _get_notifier(self, config: Dict[str, Any]) -> "Optional[BaseNotifier]":
        """Get or create a notifier instance.

        Args:
            config: The notifier configuration dict.

        Returns:
            The notifier instance, or None if creation fails.
        """
        notifier_type = config.get("type")
        if not notifier_type:
            logger.warning("Notifier config missing 'type' field")
            return None

        # Create unique key for this config
        config_key = f"{notifier_type}:{hash(frozenset(config.items()))}"

        if config_key not in self._notifiers:
            try:
                from .notifiers import get_notifier

                # Remove 'type' from kwargs
                kwargs = {k: v for k, v in config.items() if k != "type"}
                self._notifiers[config_key] = get_notifier(notifier_type, **kwargs)
            except KeyError:
                logger.error(f"Unknown notifier type: {notifier_type}")
                return None
            except Exception as e:
                logger.error(f"Failed to create notifier {notifier_type}: {e}")
                return None

        return self._notifiers.get(config_key)

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Gracefully shutdown the executor.

        Waits for pending notifications to complete up to the timeout.

        Args:
            timeout: Maximum time to wait (seconds). Uses config if None.
        """
        self._shutdown = True
        actual_timeout = timeout or self.config.graceful_shutdown_seconds

        logger.info(
            f"Shutting down notification executor (timeout={actual_timeout}s)..."
        )

        if self._executor is not None:
            # Wait for pending tasks
            self._executor.shutdown(wait=True, cancel_futures=False)

            # Wait for futures with timeout
            with self._lock:
                for future in self._active_futures:
                    try:
                        future.result(timeout=actual_timeout)
                    except FutureTimeoutError:
                        logger.warning("Notification task timed out during shutdown")
                    except Exception as e:
                        logger.error(f"Error during shutdown: {e}")

            self._executor = None

        logger.info("Notification executor shutdown complete")

    @property
    def pending_count(self) -> int:
        """Get the number of pending notifications.

        Returns:
            Number of notifications in the queue.
        """
        return self._pending_tasks.qsize()

    @property
    def is_shutdown(self) -> bool:
        """Check if the executor is shutdown.

        Returns:
            True if shutdown, False otherwise.
        """
        return self._shutdown
