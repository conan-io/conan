"""
Test that lock ordering violation error messages are helpful and actionable.
"""

import tempfile
import pytest

from conan.errors import ConanException
from conan.internal.cache.concurrency_lock import ConcurrencyLock, LockLevel


def test_lock_ordering_violation_error_message():
    """Verify lock ordering violations produce helpful error messages"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_manager = ConcurrencyLock(tmpdir)

        # Try to acquire locks in wrong order (package before recipe)
        with pytest.raises(ConanException) as exc_info:
            with lock_manager.lock("lock_recipe", level=LockLevel.RECIPE):
                # Now try to acquire a config lock (lower level) - should fail
                with lock_manager.lock("lock_config", level=LockLevel.CONFIG):
                    pass

        error_msg = str(exc_info.value)

        # Verify error message contains helpful information
        assert "Lock ordering violation" in error_msg
        assert "lock_config" in error_msg
        assert "level 10" in error_msg  # CONFIG level
        assert "lock_recipe" in error_msg
        assert "level 20" in error_msg  # RECIPE level
        assert "Currently held locks:" in error_msg
        assert "Solution:" in error_msg
        assert "Release higher-level locks" in error_msg


def test_lock_ordering_correct_order_works():
    """Verify locks can be acquired in correct order"""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_manager = ConcurrencyLock(tmpdir)

        # Correct order: config -> recipe -> source -> package
        with lock_manager.lock("lock_config", level=LockLevel.CONFIG):
            with lock_manager.lock("lock_recipe", level=LockLevel.RECIPE):
                with lock_manager.lock("lock_source", level=LockLevel.SOURCE):
                    with lock_manager.lock("lock_package", level=LockLevel.PACKAGE):
                        pass  # All locks acquired successfully
