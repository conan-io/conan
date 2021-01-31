import os

from conans.model.build_info import CppInfo


class _LayoutEntry(object):

    def __init__(self):
        self.cpp_info = CppInfo(None, None)
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

        self.source = _LayoutEntry()
        # Supported info in source layout:
        #   - self.info.includedirs
        #   - self.info.resdirs
        #   - self.info.builddirs
        self.source.include_patterns = ["*.h", "*.hpp", "*.hxx"]

        self.build = _LayoutEntry()

        self.build.lib_patterns = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.build.bin_patterns = ["*.exe", "*.dll"]

        self.package = _LayoutEntry()
        self.generators = _LayoutEntry()

    def __repr__(self):
        return str(self.__dict__)

    @property
    def source_folder(self):
        if self._base_source_folder is None:
            return None
        if not self.source.folder:
            return self._base_source_folder

        return os.path.join(self._base_source_folder, self.source.folder)

    def set_base_source_folder(self, folder):
        self._base_source_folder = folder

    @property
    def base_source_folder(self):
        return self._base_source_folder

    @property
    def build_folder(self):
        if self._base_build_folder is None:
            return None
        if not self.build.folder:
            return self._base_build_folder
        return os.path.join(self._base_build_folder, self.build.folder)

    def set_base_build_folder(self, folder):
        self._base_build_folder = folder

    @property
    def base_build_folder(self):
        return self._base_build_folder

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

    @property
    def base_package_folder(self):
        return self._base_package_folder

    def get_package_cppinfo(self, name):
        cpp_info = self.package.cpp_info
        # FIXME: Quite hacky, see if we can change the constructor of CppInfo
        cpp_info.rootpath = self.base_package_folder
        cpp_info.name = name
        cpp_info._ref_name = name
        return cpp_info

    def get_editable_cppinfo(self, name):
        # TODO: Could be improved by calculating a CppInfo from the build and source ones but using
        #      the common base editable path as root_folder and avoiding to add absolute folders here
        cpp_info = self.build.cpp_info
        # FIXME: Quite hacky, see if we can change the constructor of CppInfo
        cpp_info.rootpath = self.build_folder
        cpp_info.name = name
        cpp_info._ref_name = name
        # Append values from cpp_info from source with absolute paths both from build and source
        self.source.cpp_info.rootpath = self.source_folder
        cpp_info.includedirs.extend(self.source.cpp_info.include_paths)
        cpp_info.builddirs.extend(self.source.cpp_info.build_paths)
        cpp_info.resdirs.extend(self.source.cpp_info.res_paths)
        # TODO: only supported these things from source layout
        return cpp_info

    def generators_folder(self):
        if not self.generators.folder:
            return self.base_install_folder
        return os.path.join(self._base_generators_folder, self.generators.folder)

    def set_base_generators_folder(self, folder):
        self._base_generators_folder = folder

