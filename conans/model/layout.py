import os


class _LayoutEntry(object):

    def __init__(self):
        self.folder = ""
        self.includedirs = {}
        self.builddirs = {}
        self.resdirs = {}
        self.libdirs = {}
        self.bindirs = {}


class Layout(object):
    def __init__(self):

        self._base_source_folder = None
        self._base_build_folder = None
        self._base_install_folder = None
        self._base_package_folder = None

        self.install = _LayoutEntry()
        self.install.folder = ""

        self.build = _LayoutEntry()
        self.build.folder = ""  # Where the software is built (relative to _base_build_folder)
        self.build.libdirs[""] = ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        self.build.bindirs[""] = ["*.exe", "*.dll"]

        self.source = _LayoutEntry()
        self.source.folder = ""
        self.source.includedirs[""] = ["*.h", "*.hpp"]

        self.package = _LayoutEntry()  # Where the artifacts are installed
        self.package.includedirs["include"] = ["*"]
        self.package.bindirs["bin"] = ["*"]
        self.package.libdirs["lib"] = ["*"]

    def __str__(self):
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
    def build_folder(self):
        print("Build folder: {}".format(self._base_build_folder))
        print("Build folder: {}".format(self._base_build_folder))
        if self._base_build_folder is None:
            return None
        if not self.build.folder:
            return self._base_build_folder
        return os.path.join(self._base_build_folder, self.build.folder)

    def set_base_build_folder(self, folder):
        self._base_build_folder = folder

    @property
    def install_folder(self):
        if self._base_install_folder is None:
            return self.build_folder  # If None, default to build_folder (review)
        if not self.install.folder:
            return self._base_install_folder

        return os.path.join(self._base_install_folder, self.build.folder)

    def set_base_install_folder(self, folder):
        self._base_install_folder = folder

    @property
    def package_folder(self):
        if self._base_package_folder is None:
            return None
        if not self.package.folder:
            return self._base_package_folder

        return os.path.join(self._base_package_folder, self.package.folder)

    def set_base_package_folder(self, folder):
        self._base_package_folder = folder





    """

    def package(self, header_patterns=None, bin_patterns=None, lib_patterns=None,
                build_patterns=None, res_patterns=None):
        # FIXME: !!! PROBABLY THIS SHOULD BE DONE BY THE CONANFILE. DECLARATIVE PATTERNS MAYBE??
        header_patterns = header_patterns or ["*.h"]
        bin_patterns = bin_patterns or ["*.exe", "*.dll"]
        lib_patterns = lib_patterns or ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        build_patterns = build_patterns or []
        res_patterns = res_patterns or []
        same_src_and_build = self._base_source_folder == self._base_build_folder

        if same_src_and_build or self._base_source_folder == os.getcwd():
            for include in self.src_includedirs:
                for pat in header_patterns:
                    self._conan_file.copy(pat, dst=self.pkg_includedir, src=include)
            for pat in build_patterns:
                self._conan_file.copy(pat, dst=self.pkg_builddir, src=self.src_builddir)
            for pat in res_patterns:
                self._conan_file.copy(pat, dst=self.pkg_resdir, src=self.src_resdir)

        if self._base_build_folder == os.getcwd():
            for include in self.build_includedirs:
                for pat in header_patterns:
                    self._conan_file.copy(pat, dst=self.pkg_includedir, src=include)
            for pat in build_patterns:
                self._conan_file.copy(pat, dst=self.pkg_builddir, src=self.build_builddir,
                                      keep_path=False)
            for pat in res_patterns:
                self._conan_file.copy(pat, dst=self.pkg_resdir, src=self.build_resdir)
            for pat in lib_patterns:
                self._conan_file.copy(pat, dst=self.pkg_libdir, src=self.build_libdir)
            for pat in bin_patterns:
                self._conan_file.copy(pat, dst=self.pkg_bindir, src=self.build_bindir)

    def package_info(self):
        # FIXME: !!! PROBABLY THIS SHOULD BE DONE BY THE CONANFILE.
        # Make sure the ``package()`` and ``cpp_info`` are consistent
        self._conan_file.cpp_info.includedirs = [self.pkg_includedir]
        self._conan_file.cpp_info.libdirs = [self.pkg_libdir]
        self._conan_file.cpp_info.bindirs = [self.pkg_bindir]
        self._conan_file.cpp_info.buildirs = [self.pkg_builddir]
        """
