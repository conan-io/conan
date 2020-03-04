"""
    Exceptions raised and handled in Conan server.
    These exceptions are mapped between server (as an HTTP response) and client
    through the REST API. When an error happens in server its translated to an HTTP
    error code that its sent to client. Client reads the server code and raise the
    matching exception.

    see return_plugin.py

"""
from contextlib import contextmanager
from subprocess import CalledProcessError

from conans.util.env_reader import get_env
from conans.util.files import decode_text


class CalledProcessErrorWithStderr(CalledProcessError):
    def __str__(self):
        ret = super(CalledProcessErrorWithStderr, self).__str__()
        if self.output:
            ret += "\n" + decode_text(self.output)
        return ret


@contextmanager
def conanfile_exception_formatter(conanfile_name, func_name):
    """
    Decorator to throw an exception formatted with the line of the conanfile where the error ocurrs.
    :param reference: Reference of the conanfile
    :return:
    """
    try:
        yield
    except ConanInvalidConfiguration as exc:
        msg = "{}: Invalid configuration: {}".format(conanfile_name, exc)  # TODO: Move from here?
        raise ConanInvalidConfiguration(msg)
    except Exception as exc:
        msg = _format_conanfile_exception(conanfile_name, func_name, exc)
        raise ConanExceptionInUserConanfileMethod(msg)


def _format_conanfile_exception(scope, method, exception):
    """
    It will iterate the traceback lines, when it finds that the source code is inside the users
    conanfile it "start recording" the messages, when the trace exits the conanfile we return
    the traces.
    """
    import sys
    import traceback
    if get_env("CONAN_VERBOSE_TRACEBACK", False):
        return traceback.format_exc()
    try:
        conanfile_reached = False
        tb = sys.exc_info()[2]
        index = 0
        content_lines = []

        while True:  # If out of index will raise and will be captured later
            # 40 levels of nested functions max, get the latest
            filepath, line, name, contents = traceback.extract_tb(tb, 40)[index]
            if "conanfile.py" not in filepath:  # Avoid show trace from internal conan source code
                if conanfile_reached:  # The error goes to internal code, exit print
                    break
            else:
                if not conanfile_reached:  # First line
                    msg = "%s: Error in %s() method" % (scope, method)
                    msg += ", line %d\n\t%s" % (line, contents)
                else:
                    msg = ("while calling '%s', line %d\n\t%s" % (name, line, contents)
                           if line else "\n\t%s" % contents)
                content_lines.append(msg)
                conanfile_reached = True
            index += 1
    except Exception:
        pass
    ret = "\n".join(content_lines)
    ret += "\n\t%s: %s" % (exception.__class__.__name__, str(exception))
    return ret


class ConanException(Exception):
    """
         Generic conans exception
    """
    def __init__(self, *args, **kwargs):
        self.info = None
        self.remote = kwargs.pop("remote", None)
        super(ConanException, self).__init__(*args, **kwargs)

    def remote_message(self):
        if self.remote:
            return " [Remote: {}]".format(self.remote.name)
        return ""

    def __str__(self):
        from conans.util.files import exception_message_safe
        msg = super(ConanException, self).__str__()
        if self.remote:
            return "{}.{}".format(exception_message_safe(msg), self.remote_message())

        return exception_message_safe(msg)


class ConanV2Exception(ConanException):
    def __str__(self):
        msg = super(ConanV2Exception, self).__str__()
        # TODO: Add a link to a public webpage with Conan roadmap to v2
        return "Conan v2 incompatible: {}".format(msg)


class OnlyV2Available(ConanException):

    def __init__(self, remote_url):
        msg = "The remote at '%s' only works with revisions enabled. " \
              "Set CONAN_REVISIONS_ENABLED=1 " \
              "or set 'general.revisions_enabled = 1' at the 'conan.conf'" % remote_url
        super(OnlyV2Available, self).__init__(msg)


class NoRestV2Available(ConanException):
    pass


class NoRemoteAvailable(ConanException):
    """ No default remote configured or the specified remote do not exists
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


class ConanInvalidConfiguration(ConanExceptionInUserConanfileMethod):
    pass


class ConanMigrationError(ConanException):
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

    def __init__(self, *args, **kwargs):
        self.remote = kwargs.pop("remote", None)
        super(NotFoundException, self).__init__(*args, **kwargs)


class RecipeNotFoundException(NotFoundException):

    def __init__(self, ref, remote=None, print_rev=False):
        from conans.model.ref import ConanFileReference
        assert isinstance(ref, ConanFileReference), "RecipeNotFoundException requires a " \
                                                    "ConanFileReference"
        self.ref = ref
        self.print_rev = print_rev
        super(RecipeNotFoundException, self).__init__(remote=remote)

    def __str__(self):
        tmp = self.ref.full_str() if self.print_rev else str(self.ref)
        return "Recipe not found: '{}'".format(tmp, self.remote_message())


class PackageNotFoundException(NotFoundException):

    def __init__(self, pref, remote=None, print_rev=False):
        from conans.model.ref import PackageReference
        assert isinstance(pref, PackageReference), "PackageNotFoundException requires a " \
                                                   "PackageReference"
        self.pref = pref
        self.print_rev = print_rev

        super(PackageNotFoundException, self).__init__(remote=remote)

    def __str__(self):
        tmp = self.pref.full_str() if self.print_rev else str(self.pref)
        return "Binary package not found: '{}'{}".format(tmp, self.remote_message())


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
                          RecipeNotFoundException: 404,
                          PackageNotFoundException: 404,
                          UserInterfaceErrorException: 420}
