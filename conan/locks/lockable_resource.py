class LockableResource:
    # TODO: Remove
    def __init__(self, manager: 'LocksManager', resource: str, blocking: bool, wait: bool):
        self._manager = manager
        self._resource = resource
        self._bloking = blocking
        self._wait = wait
        self._lock_handler = None

    def __enter__(self):
        self._lock_handler = self._manager.try_acquire(self._resource, self._bloking, self._wait)

    def __exit__(self, type, value, traceback):
        assert self._lock_handler
        self._manager.release(self._lock_handler)
