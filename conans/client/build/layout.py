import os


class DefaultLayout(object):
    def __init__(self, conan_file):
        self._conan_file = conan_file

        # Build layout
        self.build = "build"
        self.src = ""
        # TODO: To discuss, are we sure we want only 1 value?
        self.build_libdir = ""  # Relative to self.build
        # TODO: To discuss, are we sure we want only 1 value?
        self.build_bindir = ""  # Relative to self.build
        # Relative to root, needed to specify "build/x" or "src/x"
        self.build_includedirs = [self.build, self.src]
        self.build_installdir = None  # Relative to root
        self.build_builddir = ""  # Relative to root
        self.build_resdir = ""  # Relative to root

        self.pkg_libdir = "lib"
        self.pkg_bindir = "bin"
        self.pkg_includedir = "include"
        self.pkg_builddir = ""
        self.pkg_resdir = ""

    def __str__(self):
        return str(self.__dict__)

    # Getters, relative to base
    @property
    def build_lib_folder(self):
        return os.path.join(self.build, self.build_libdir)

    @property
    def build_bin_folder(self):
        return os.path.join(self.build, self.build_bindir)

    @property
    def build_install_folder(self):
        return self.build_installdir if self.build_installdir is not None else self.build

    # Getters, useful for recipes, relative to self._conanfile.xxx
    @property
    def build_folder(self):
        return os.path.join(self._conan_file.build_folder, self.build)

    @property
    def source_folder(self):
        return os.path.join(self._conan_file.source_folder, self.src)

    def package(self, header_patterns=None, bin_patterns=None, lib_patterns=None,
                build_patterns=None, res_patterns=None):

        header_patterns = header_patterns or ["*.h"]
        bin_patterns = bin_patterns or ["*.exe", "*.dll"]
        lib_patterns = lib_patterns or ["*.so", "*.so.*", "*.a", "*.lib", "*.dylib"]
        build_patterns = build_patterns or []
        res_patterns = res_patterns or []

        for include in self.build_includedirs:
            for pat in header_patterns:
                self._conan_file.copy(pat, dst=self.pkg_includedir,
                                      src=include, keep_path=False)
        for pat in lib_patterns:
            self._conan_file.copy(pat, dst=self.pkg_libdir,
                                  src=self.build_lib_folder, keep_path=False)
        for pat in bin_patterns:
            self._conan_file.copy(pat, dst=self.pkg_bindir,
                                  src=self.build_bin_folder, keep_path=False)
        for pat in build_patterns:
            self._conan_file.copy(pat, dst=self.pkg_builddir,
                                  src=self.build_builddir, keep_path=False)
        for pat in res_patterns:
            self._conan_file.copy(pat, dst=self.pkg_resdir,
                                  src=self.build_resdir, keep_path=False)

    def imports(self, bin_patterns=None, lib_patterns=None, build_patterns=None, res_patterns=None):
        bin_patterns = bin_patterns or ["*.exe", "*.dll"]
        lib_patterns = lib_patterns or ["*.so", "*.so.*", "*.dylib"]
        build_patterns = build_patterns or []
        res_patterns = res_patterns or []

        for pat in lib_patterns:
            self._conan_file.copy(pat, dst=self.build_lib_folder, src="@libdirs", keep_path=False)
        for pat in bin_patterns:
            self._conan_file.copy(pat, dst=self.build_bin_folder, src="@bindirs", keep_path=False)
        for pat in build_patterns:
            self._conan_file.copy(pat, dst=self.build_builddir, src="@builddirs", keep_path=False)
        for pat in res_patterns:
            self._conan_file.copy(pat, dst=self.build_resdir, src="@resdirs", keep_path=False)

    def package_info(self):
        # Make sure the ``package()`` and ``cpp_info`` are consistent
        self._conan_file.cpp_info.includedirs = [self.pkg_includedir]
        self._conan_file.cpp_info.libdirs = [self.pkg_libdir]
        self._conan_file.cpp_info.bindirs = [self.pkg_bindir]
        self._conan_file.cpp_info.buildirs = [self.pkg_builddir]


class CMakeLayout(DefaultLayout):
    """
        /CMakeLists.txt
        /src/foo.h
        /src/foo.cpp
        /build/Release/<build files> <= Visual only
        /cmake-build-release/<build files> <= Others, when
        /build <=
    """
    def __init__(self, conanfile):
        super(CMakeLayout, self).__init__(conanfile)
        # Only input to build is the source directory, include not a thing here
        # relative to conanfile
        self.src = ""
        # Output of build, relative to conanfile
        self.build = "build"
        # Output of build, relative to self.build_folder
        build_type = conanfile.settings.get_safe("build_type")
        # NOTE: This is false, only when the generator is visual studio
        #       in that case the user has to redeclare the layout, this is just a
        #       good-enough-general-purpose template
        if conanfile.settings.get_safe("compiler") == "Visual Studio":
            self.build_libdir = str(build_type)
            self.build_bindir = str(build_type)
        else:
            if conanfile.settings.get_safe("build_type"):
                build_type = conanfile.settings.get_safe("build_type") or "release"
                self.build = "cmake-build-{}".format(str(build_type.lower()))
            else:
                self.build = "build"
        self.build_includedirs = [self.build, "src"]
