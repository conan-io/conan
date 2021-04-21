import os

from conans.client.file_copier import FileCopier
from conans.errors import ConanException
from conans.util.log import logger


class _FoldersEntry(object):

    def __init__(self):
        self.include_patterns = []
        self.lib_patterns = []
        self.bin_patterns = []
        self.src_patterns = []
        self.build_patterns = []
        self.res_patterns = []
        self.framework_patterns = []
        self.folder = ""


class Folders(object):
    def __init__(self):

        self._base_install = None
        self._base_source = None
        self._base_build = None
        self._base_package = None
        self._base_generators = None

        self.source = _FoldersEntry()

        self.source.include_patterns = ["*.h", "*.hpp", "*.hxx"]

        self.build = _FoldersEntry()
        self.build.lib_patterns = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.build.bin_patterns = ["*.exe", "*.dll"]

        self.package = _FoldersEntry()
        self.generators = _FoldersEntry()

    def __repr__(self):
        return str(self.__dict__)

    @property
    def source_folder(self):
        if self._base_source is None:
            return None
        if not self.source.folder:
            return self._base_source

        return os.path.join(self._base_source, self.source.folder)

    @property
    def base_source(self):
        return self._base_source

    def set_base_source(self, folder):
        self._base_source = folder

    @property
    def build_folder(self):
        if self._base_build is None:
            return None
        if not self.build.folder:
            return self._base_build
        return os.path.join(self._base_build, self.build.folder)

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
    def generators_folder(self):
        if self._base_generators is None:
            return None
        if not self.generators.folder:
            return self._base_generators
        return os.path.join(self._base_generators, self.generators.folder)

    def set_base_generators(self, folder):
        self._base_generators = folder
