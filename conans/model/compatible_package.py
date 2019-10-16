class CompatiblePackage(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._settings = None
        self._options = None
        self._requires = None

    @property
    def settings(self):
        if not self._settings:
            self._settings = self._conanfile.settings.copy()
        return self._settings

    @property
    def options(self):
        if not self._options:
            self._options = self._conanfile.options.copy()
        return self._options

    @property
    def requires(self):
        if not self._requires:
            self._requires = self._conanfile.info.requires.copy()
        return self._requires

    def package_id(self):
        info = self._conanfile.info.copy()
        if self._settings:
            info.settings = self._settings.values
        if self._options:
            info.options = self._options.values
            info.options.clear_indirect()
        if self._requires:
            info.requires = self._requires
        return info.package_id()
