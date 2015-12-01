'''
    Exceptions raised and handled in Conan server.
    These exceptions are mapped between server (as an HTTP response) and client
    through the REST API. When an error happens in server its translated to an HTTP
    error code that its sent to client. Client reads the server code and raise the
    matching exception.

    see return_plugin.py

'''


class ConanException(Exception):
    """
         Generic conans exception
    """
    pass


class InvalidNameException(ConanException):
    pass


class ConanConnectionError(ConanException):
    pass


class ConanOutdatedClient(ConanException):
    pass


# Remote exceptions #

class InternalErrorException(ConanException):
    """
         Generic 500 error
    """
    pass


class RequestErrorException(ConanException):
    """
         Generic 400 error
    """
    pass


class AuthenticationException(ConanException):  # 401
    """
        401 error
    """
    pass


class ForbiddenException(ConanException):  # 403
    """
        403 error
    """
    pass


class NotFoundException(ConanException):  # 404
    """
        404 error
    """
    pass


class UserInterfaceErrorException(RequestErrorException):
    """
        420 error
    """
    pass


EXCEPTION_CODE_MAPPING = {InternalErrorException: 500,
                          RequestErrorException: 400,
                          AuthenticationException: 401,
                          ForbiddenException: 403,
                          NotFoundException: 404,
                          UserInterfaceErrorException: 420}
