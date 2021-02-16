from conans.errors import ConanException


class AlreadyLockedException(ConanException):
    def __init__(self, resource: str, by_writer: bool = False):
        msg = f"Resource '{resource}' is already blocked"
        if by_writer:
            msg += ' by a writer'
        super().__init__(msg)
