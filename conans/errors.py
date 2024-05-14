"""
    Exceptions raised and handled in Conan
    These exceptions are mapped between server (as an HTTP response) and client
    through the REST API. When an error happens in server its translated to an HTTP
    error code that its sent to client. Client reads the server code and raise the
    matching exception.

    see return_plugin.py

"""
from contextlib import contextmanager


@contextmanager
def conanfile_remove_attr(conanfile, names, method):
    """ remove some self.xxxx attribute from the class, so it raises an exception if used
    within a given conanfile method
    """
    original_class = type(conanfile)

    def _prop(attr_name):
        def _m(_):
            raise ConanException(f"'self.{attr_name}' access in '{method}()' method is forbidden")
        return property(_m)

    try:
        new_class = type(original_class.__name__, (original_class, ), {})
        conanfile.__class__ = new_class
        for name in names:
            setattr(new_class, name, _prop(name))
        yield
    finally:
        conanfile.__class__ = original_class


@contextmanager
def conanfile_exception_formatter(conanfile_name, func_name):
    """
    Decorator to throw an exception formatted with the line of the conanfile where the error ocurrs.
    """

    def _raise_conanfile_exc(e):
        from conan.api.output import LEVEL_DEBUG, ConanOutput
        if ConanOutput.level_allowed(LEVEL_DEBUG):
            import traceback
            raise ConanException(traceback.format_exc())
        m = scoped_traceback(f"{conanfile_name}: Error in {func_name}() method", e,
                             scope="conanfile.py")
        raise ConanException(m)

    try:
        yield
    # TODO: Move ConanInvalidConfiguration from here?
    except ConanInvalidConfiguration as exc:
        msg = "{}: Invalid configuration: {}".format(str(conanfile_name), exc)
        raise ConanInvalidConfiguration(msg)
    except AttributeError as exc:
        list_methods = [m for m in dir(list) if not m.startswith('__')]
        if "NoneType" in str(exc) and func_name in ['layout', 'package_info'] and \
            any(method in str(exc) for method in list_methods):
            raise ConanException("{}: {}. No default values are set for components. You are probably "
                                 "trying to manipulate a component attribute in the '{}' method "
                                 "without defining it previously".format(str(conanfile_name), exc, func_name))
        else:
            _raise_conanfile_exc(exc)
    except Exception as exc:
        _raise_conanfile_exc(exc)


def scoped_traceback(header_msg, exception, scope):
    """
    It will iterate the traceback lines, when it finds that the source code is inside the users
    conanfile it "start recording" the messages, when the trace exits the conanfile we return
    the traces.
    """
    import sys
    import traceback
    content_lines = []
    try:
        scope_reached = False
        tb = sys.exc_info()[2]
        index = 0

        while True:  # If out of index will raise and will be captured later
            # 40 levels of nested functions max, get the latest
            filepath, line, name, contents = traceback.extract_tb(tb, 40)[index]
            filepath = filepath.replace("\\", "/")
            if scope not in filepath:  # Avoid show trace from internal conan source code
                if scope_reached:  # The error goes to internal code, exit print
                    break
            else:
                if not scope_reached:  # First line
                    msg = f"{header_msg}, line {line}\n\t{contents}"
                else:
                    msg = (f"while calling '{name}', line {line}\n\t{contents}"
                           if line else "\n\t%s" % contents)
                content_lines.append(msg)
                scope_reached = True
            index += 1
    except IndexError:
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


class ConanReferenceDoesNotExistInDB(ConanException):
    """ Reference does not exist in cache db """
    pass


class ConanReferenceAlreadyExistsInDB(ConanException):
    """ Reference already exists in cache db """
    pass


class NoRemoteAvailable(ConanException):
    """ No default remote configured or the specified remote do not exists
    """
    pass


class ConanConnectionError(ConanException):
    pass


class ConanInvalidConfiguration(ConanException):
    """
    This binary, for the requested configuration and package-id cannot be built
    """
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

    def __init__(self, ref, remote=None):
        from conans.model.recipe_ref import RecipeReference
        assert isinstance(ref, RecipeReference), "RecipeNotFoundException requires a RecipeReference"
        self.ref = ref
        super(RecipeNotFoundException, self).__init__(remote=remote)

    def __str__(self):
        tmp = repr(self.ref)
        return "Recipe not found: '{}'".format(tmp, self.remote_message())


class PackageNotFoundException(NotFoundException):

    def __init__(self, pref, remote=None):
        from conans.model.package_ref import PkgReference
        assert isinstance(pref, PkgReference), "PackageNotFoundException requires a PkgReference"
        self.pref = pref

        super(PackageNotFoundException, self).__init__(remote=remote)

    def __str__(self):
        return "Binary package not found: '{}'{}".format(self.pref.repr_notime(),
                                                         self.remote_message())


EXCEPTION_CODE_MAPPING = {InternalErrorException: 500,
                          RequestErrorException: 400,
                          AuthenticationException: 401,
                          ForbiddenException: 403,
                          NotFoundException: 404,
                          RecipeNotFoundException: 404,
                          PackageNotFoundException: 404}
