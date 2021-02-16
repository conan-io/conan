from io import StringIO


class LockBackend:
    LockId = None

    def dump(self, output: StringIO):
        raise NotImplementedError

    def try_acquire(self, resource: str, blocking: bool) -> LockId:
        # Returns a backend-id
        raise NotImplementedError

    def release(self, backend_id: LockId):
        raise NotImplementedError
