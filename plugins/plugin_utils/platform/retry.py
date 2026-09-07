# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Tom Page <tpage@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Retry logic for Automation Orchestrator API operations."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import functools
import logging
import random
import time
from typing import Callable, Optional, TypeVar

from .exceptions import AOError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(self, max_attempts: int = 3, initial_delay: float = 1.0, max_delay: float = 60.0, exponential_base: float = 2.0, jitter: bool = True):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        delay = self.initial_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)
        if self.jitter:
            jitter_amount = delay * 0.1
            delay = max(0, delay + random.uniform(-jitter_amount, jitter_amount))
        return delay


DEFAULT_RETRY_CONFIG = RetryConfig(max_attempts=3, initial_delay=1.0, max_delay=60.0, exponential_base=2.0, jitter=True)


def retry_on_failure(config: Optional[RetryConfig] = None, retryable_exceptions: Optional[tuple] = None) -> Callable:
    """Decorator for retrying operations on transient (retryable) failures."""
    if config is None:
        config = DEFAULT_RETRY_CONFIG
    if retryable_exceptions is None:
        retryable_exceptions = (AOError,)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exception = exc
                    is_retryable = getattr(exc, "retryable", False) if isinstance(exc, AOError) else isinstance(exc, retryable_exceptions)
                    if not is_retryable or attempt == config.max_attempts - 1:
                        raise
                    delay = config.calculate_delay(attempt)
                    logger.warning(
                        "Retrying %s (attempt %s/%s) after %.2fs: %s: %s",
                        func.__name__,
                        attempt + 1,
                        config.max_attempts,
                        delay,
                        type(exc).__name__,
                        exc,
                    )
                    time.sleep(delay)
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Retry logic failed for {func.__name__}")

        return wrapper

    return decorator
