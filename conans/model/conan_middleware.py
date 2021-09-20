from conans.errors import ConanInvalidConfiguration
from conans.model.values import Values

def create_settings(middleware, settings):
    try:
        defined_settings = getattr(middleware, "settings_middleware", None)
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

    def __init__(self, conanfile_or_middleware, attrs=()):
        super().__setattr__("_attrs", ["_attrs", "conanfile", "settings_middleware"] + list(attrs))
        self.conanfile = conanfile_or_middleware

    def get_conanfile(self):
        result = self.conanfile
        while result and isinstance(result, Middleware):
            result = result.conanfile
        return result

    def __getattr__(self, name):
        return getattr(self.conanfile, name)

    def __setattr__(self, name, value):
        if name in self._attrs:
            super().__setattr__(name, value)
        else:
            setattr(self.conanfile, name, value)

    def __delattr__(self, name, value):
        if name in self._attrs:
            super().__delattr__(name, value)
        else:
            delattr(self.conanfile, name, value)

    def __eq__(self, other):
        return self.conanfile == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.conanfile)

    def __repr__(self):
        return repr(self.conanfile)

    def initialize(self, settings):
        self.settings_middleware = create_settings(self, settings)

    def system_requirements(self):
        """ This must be defined for installer.py so type(conanfile).system_requirements exists. """
        return self.conanfile.system_requirements()

    def package_id(self):
        settings_middleware = self.settings_middleware.values_list
        if settings_middleware:
            self.info.settings = Values.from_list(settings_middleware + self.info.settings.as_list())
