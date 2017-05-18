"""
    Exceptions raised and handled in Conan server.
    These exceptions are mapped between server (as an HTTP response) and client
    through the REST API. When an error happens in server its translated to an HTTP
    error code that its sent to client. Client reads the server code and raise the
    matching exception.

    see return_plugin.py

"""

from contextlib import contextmanager


@contextmanager
def conanfile_exception_formatter(conanfile_name, func_name):
    """
    Decorator to throw an exception formatted with the line of the conanfile where the error ocurrs.
    :param reference: Reference of the conanfile
    :return:
    """
    try:
        yield
    except Exception as exc:
        msg = _format_conanfile_exception(conanfile_name, func_name, exc)
        raise ConanExceptionInUserConanfileMethod(msg)


def _format_conanfile_exception(scope, method, exception):
    import sys
    import traceback
    msg = "%s: Error in %s() method" % (scope, method)
    try:
        tb = sys.exc_info()[2]
        index = -1
        while True:  # If out of index will raise and will be captured later
            filepath, line, name, contents = traceback.extract_tb(tb, 40)[index]  # 40 levels of nested functions max, get the latest
            if not "conanfile.py" in filepath: # Avoid show trace from internal conan source code
                index -= 1
            else:
                break
        if name != method:
            msg += ", while calling '%s'" % name
        msg += ", line %d\n\t%s" % (line, contents) if line else "\n\t%s" % contents
    except:
        pass
    msg += "\n\t%s: %s" % (exception.__class__.__name__, str(exception))
    return msg


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


class ConanExceptionInUserConanfileMethod(ConanException):
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
