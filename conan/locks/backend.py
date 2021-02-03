class LockBackend:
    LockId = None

    def try_acquire(self, resource: str, blocking: bool) -> LockId:
        # Returns a backend-id
        raise NotImplementedError

    def release(self, backend_id: LockId):
        raise NotImplementedError
