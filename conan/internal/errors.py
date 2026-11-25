import traceback
from contextlib import contextmanager

from conan.errors import ConanException, ConanInvalidConfiguration


def _forbidden_prop(attr_name, method):
    def _m(_):
        raise ConanException(f"'self.{attr_name}' access in '{method}()' method is forbidden")
    return property(_m)


def _forbidden_class(original_class, names, method):
    """ The subclass of a recipe class whose ``names`` attributes raise if used within ``method``.
    Created once per recipe class, method and names, not in every call: creating a class took
    ~8 us and left ~3 KB of objects in reference cycles, never freed with the cyclic garbage
    collector disabled. Kept in the recipe class itself, not inherited, so it lives as long as it
    """
    classes = original_class.__dict__.get("_conan_forbidden_classes")
    if classes is None:
        classes = {}
        setattr(original_class, "_conan_forbidden_classes", classes)
    key = (method, names)
    new_class = classes.get(key)
    if new_class is None:
        attrs = {name: _forbidden_prop(name, method) for name in names}
        new_class = type(original_class.__name__, (original_class, ), attrs)
        classes[key] = new_class
    return new_class


@contextmanager
def conanfile_remove_attr(conanfile, names, method):
    """ remove some self.xxxx attribute from the class, so it raises an exception if used
    within a given conanfile method
    """
    # A tuple, part of the key of the cached subclass. Not a str, like ("info") without the comma
    assert isinstance(names, tuple), names
    original_class = type(conanfile)
    try:
        conanfile.__class__ = _forbidden_class(original_class, names, method)
        yield
    finally:
        conanfile.__class__ = original_class


@contextmanager
def conanfile_exception_formatter(conanfile, funcname, ref=None):
    """
    Decorator to throw an exception formatted with the line of the conanfile where the error ocurrs.
    """
    try:
        yield
    except ConanInvalidConfiguration as exc:
        # TODO: This is never called from `conanfile.validate()` but could be called from others
        header = ref if ref is not None else str(conanfile)
        header = f"{header}: " if header else ""
        msg = f"{header}Invalid configuration: {exc}"
        raise ConanInvalidConfiguration(msg)
    except Exception as exc:
        header = ref if ref is not None else str(conanfile)
        header = f"{header}: " if header else ""
        m = scoped_traceback(f"{header}Error in {funcname}() method", exc, scope="conanfile.py")
        from conan.api.output import LEVEL_DEBUG, ConanOutput
        if ConanOutput.level_allowed(LEVEL_DEBUG):
            m = traceback.format_exc() + "\n" + m
        raise ConanException(m)


def scoped_traceback(header_msg, exception, scope):
    """
    It will iterate the traceback lines, when it finds that the source code is inside the users
    conanfile it "start recording" the messages, when the trace exits the conanfile we return
    the traces.
    """
    import sys
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


class ConanReferenceDoesNotExistInDB(ConanException):
    """ Reference does not exist in cache db """
    pass


class ConanReferenceAlreadyExistsInDB(ConanException):
    """ Reference already exists in cache db """
    pass


class ConanConnectionError(ConanException):
    pass


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


class RecipeNotFoundException(NotFoundException):

    def __init__(self, ref):
        super().__init__(f"Recipe not found: '{ref.repr_notime()}'")


class PackageNotFoundException(NotFoundException):

    def __init__(self, pref):
        super().__init__(f"Binary package not found: '{pref.repr_notime()}'")


EXCEPTION_CODE_MAPPING = {InternalErrorException: 500,
                          RequestErrorException: 400,
                          AuthenticationException: 401,
                          ForbiddenException: 403,
                          NotFoundException: 404,
                          RecipeNotFoundException: 404,
                          PackageNotFoundException: 404}
