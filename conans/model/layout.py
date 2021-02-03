import os

from conans.model.build_info import CppInfo

class CppInfoDefaultValues(object):

    def __init__(self, includedir, libdir, bindir, resdir, builddir, frameworkdir):
        self.includedir = includedir
        self.libdir = libdir
        self.bindir = bindir
        self.resdir = resdir
        self.builddir = builddir
        self.frameworkdir = frameworkdir


class _LayoutEntry(object):

    def __init__(self, default_cpp_info_values):
        self.cpp_info = CppInfo(None, None, default_values=default_cpp_info_values)

        self.include_patterns = []
        self.lib_patterns = []
        self.bin_patterns = []
        self.folder = ""


class Layout(object):
    def __init__(self):

        self._base_install_folder = None
        self._base_source_folder = None
        self._base_build_folder = None
        self._base_package_folder = None
        self._base_generators_folder = None

        source_defaults = CppInfoDefaultValues("include", None, None, None, None, None)
        self.source = _LayoutEntry(source_defaults)
        self.source.include_patterns = ["*.h", "*.hpp", "*.hxx"]

        build_defaults = CppInfoDefaultValues(None, ".", None, None, None, None)
        self.build = _LayoutEntry(build_defaults)
        self.build.lib_patterns = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.build.bin_patterns = ["*.exe", "*.dll"]

        self.package = _LayoutEntry(None)

        generators_defaults = CppInfoDefaultValues(None, None, None, None, None, None)
        self.generators = _LayoutEntry(generators_defaults)

    def __repr__(self):
        return str(self.__dict__)

    @property
    def source_folder(self):
        if self._base_source_folder is None:
            return None
        if not self.source.folder:
            return self._base_source_folder

        return os.path.join(self._base_source_folder, self.source.folder)

    @property
    def base_source_folder(self):
        return self._base_source_folder

    def set_base_source_folder(self, folder):
        self._base_source_folder = folder
        self.source.cpp_info.rootpath = self.source_folder

    @property
    def build_folder(self):
        if self._base_build_folder is None:
            return None
        if not self.build.folder:
            return self._base_build_folder
        return os.path.join(self._base_build_folder, self.build.folder)

    @property
    def base_build_folder(self):
        return self._base_build_folder

    def set_base_build_folder(self, folder):
        self._base_build_folder = folder
        self.build.cpp_info.rootpath = self.build_folder

    @property
    def base_install_folder(self):
        return self._base_install_folder

    def set_base_install_folder(self, folder):
        self._base_install_folder = folder

    @property
    def base_package_folder(self):
        return self._base_package_folder

    def set_base_package_folder(self, folder):
        self._base_package_folder = folder
        self.package.cpp_info.rootpath = folder

    @property
    def generators_folder(self):
        if not self.generators.folder:
            return self.base_install_folder
        return os.path.join(self._base_generators_folder, self.generators.folder)

    def set_base_generators_folder(self, folder):
        self._base_generators_folder = folder
