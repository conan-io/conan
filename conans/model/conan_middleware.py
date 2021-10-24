import inspect
import os

from conans.client.output import ScopedOutput
from conans.errors import ConanException, ConanInvalidConfiguration
from conans.model.values import Values
from conans.util.conan_v2_mode import conan_v2_error


def create_options(middleware):
    # avoid circular imports
    from conans.model.conan_file import create_options
    return create_options(middleware)

def create_settings(middleware, settings):
    try:
        defined_settings = getattr(middleware, "settings", None)
        if isinstance(defined_settings, str):
            defined_settings = [defined_settings]
        current = defined_settings or {}
        settings.constraint(current)
        return settings
    except Exception as e:
        raise ConanInvalidConfiguration("The middleware %s is constraining settings. %s" % (
                                        middleware.display_name, str(e)))


class Middleware(object):
    """ The base class for all middleware
    """

    name = None
    version = None  # Any str, can be "1.1" or whatever
    url = None  # The URL where this File is located, as github, to collaborate in package
    # The license of the PACKAGE, just a shortcut, does not replace or
    # change the actual license of the source code
    license = None
    author = None  # Main maintainer/responsible for the package, any format
    description = None
    topics = None
    homepage = None

    # Settings and Options
    settings = None
    options = None
    default_options = None

    def __init__(self, output, display_name=""):
        # an output stream (writeln, info, warn error)
        self.output = ScopedOutput(display_name, output)
        self.display_name = display_name

    def initialize(self, settings, env, buildenv=None):
        self._conan_buildenv = buildenv
        # User defined options
        self.options = create_options(self)
        self.settings = create_settings(self, settings)

    def config_options(self):
        """ modify options, probably conditioned to some settings. This call is executed
        before config_settings. E.g.
        if self.settings.os == "Windows":
            del self.options.shared  # shared/static not supported in win
        """

    def configure(self):
        """ modify settings, probably conditioned to some options. This call is executed
        after config_options. E.g.
        if self.options.header_only:
            self.settings.clear()
        This is also the place for conditional requirements
        """

    @staticmethod
    def extend(a, b):
        if a is None:
            return b
        elif b is None:
            return a
        elif isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
            return tuple(a) + tuple(b)
        elif isinstance(a, dict) and isinstance(b, dict):
            c = a.copy()
            c.update(b)
            return c
        else:
            raise TypeError("extend expects tuples/lists or dicts")

    @staticmethod
    def is_binary(conanfile):
        """ does this ConanFile class or instance produce binaries?
        For conanfile.txt base will be None.
        """
        if inspect.isclass(conanfile):
            # We can't see values yet
            settings = conanfile.settings
            if not (settings and "os" in settings and "arch" in settings):
                return False
        elif conanfile:
            try:
                if conanfile.options.header_only:
                    # Header only
                    return False
            except ConanException:
                pass
            try:
                conanfile.settings.arch
                conanfile.settings.os
            except ConanException:
                # arch or os is not required
                return False
        return True

    def should_apply(self, base):
        """  should this middleware be applied to a given base class?
        base is a subclass of ConanFile not an instance.
        For conanfile.txt base will be None.
        """
        return True

    def __call__(self, base):
        """  apply this middleware to a given base class.
        base is a subclass of ConanFile not an instance.
        Returns a new subclass of ConanFile.
        """
        return base

    def __repr__(self):
        return self.display_name
