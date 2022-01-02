import os

from conans.model.new_build_info import NewCppInfo


class Infos(object):

    def __init__(self):
        self.source = NewCppInfo()
        self.build = NewCppInfo()
        self.package = NewCppInfo()


class Folders(object):

    def __init__(self):
        self._base_install = None
        self._base_source = None
        self._base_build = None
        self._base_package = None
        self._base_generators = None
        self._base_imports = None

        self.source = ""
        self.build = ""
        self.package = ""
        self.generators = ""
        self.imports = ""

    def __repr__(self):
        return str(self.__dict__)

    @property
    def source_folder(self):
        if self._base_source is None:
            return None
        if not self.source:
            return self._base_source

        return os.path.join(self._base_source, self.source)

    @property
    def base_source(self):
        return self._base_source

    def set_base_source(self, folder):
        self._base_source = folder

    @property
    def build_folder(self):
        if self._base_build is None:
            return None
        if not self.build:
            return self._base_build
        return os.path.join(self._base_build, self.build)

    @property
    def base_build(self):
        return self._base_build

    def set_base_build(self, folder):
        self._base_build = folder

    @property
    def base_install(self):
        return self._base_install

    def set_base_install(self, folder):
        self._base_install = folder

    @property
    def base_package(self):
        return self._base_package

    def set_base_package(self, folder):
        self._base_package = folder

    @property
    def package_folder(self):
        """For the cache, the package folder is only the base"""
        return self._base_package

    @property
    def generators_folder(self):
        if self._base_generators is None:
            return None
        if not self.generators:
            return self._base_generators
        return os.path.join(self._base_generators, self.generators)

    def set_base_generators(self, folder):
        self._base_generators = folder

    @property
    def imports_folder(self):
        if self._base_imports is None:
            return None
        if not self.imports:
            return self._base_imports

        return os.path.join(self._base_imports, self.imports)

    @property
    def base_imports(self):
        return self._base_imports

    def set_base_imports(self, folder):
        self._base_imports = folder
