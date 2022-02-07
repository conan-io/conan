import os

from conans.model.build_info import CppInfo


class Infos(object):

    def __init__(self):
        self.source = CppInfo()
        self.build = CppInfo()
        self.package = CppInfo(set_defaults=True)


class Folders(object):

    def __init__(self):
        self._base_install = None
        self._base_source = None
        self._base_build = None
        self._base_package = None
        self._base_generators = None

        self.source = ""
        self.build = ""
        self.package = ""
        self.generators = ""

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
