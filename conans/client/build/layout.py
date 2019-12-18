import os


class Layout(object):
    def __init__(self, conan_file):
        self._conan_file = conan_file

        # Build layout
        self.build = "build"
        self.src = ""
        # TODO: To discuss, are we sure we want only 1 value?
        self.build_libdir = ""  # Relative to self.build
        # TODO: To discuss, are we sure we want only 1 value?
        self.build_bindir = ""  # Relative to self.build
        self.build_includedirs = [""]  # Relative to self.build (and or self.src)
        self.build_installdir = None  # Not relative to self.build

        self.pkg_libdir = "lib"
        self.pkg_bindir = "bin"
        self.pkg_includedir = "include"
        self.pkg_builddir = "build"

    # Getters, relative to base
    @property
    def build_lib_folder(self):
        return os.path.join(self.build, self.build_libdir)

    @property
    def build_bin_folder(self):
        return os.path.join(self.build, self.build_bindir)

    @property
    def build_include_folders(self):
        return [os.path.join(self.build, f) for f in self.build_includedirs]

    @property
    def build_install_folder(self):
        return self.build_installdir if self.build_installdir is not None else self.build

    # Getters, useful for recipes, relative to self._conanfile.xxx
    @property
    def install_folder(self):
        installdir = self.build_installdir if self.build_installdir is not None \
            else self.build
        return os.path.join(self._conan_file.install_folder, installdir)

    @property
    def build_folder(self):
        return os.path.join(self._conan_file.build_folder, self.build)

    @property
    def source_folder(self):
        return os.path.join(self._conan_file.source_folder, self.src)

    def package(self):
        # FIXME: Not very flexible. Useless? What if I want to copy only some patterns
        #        Good enough for default?
        #        Proposal kwargs: header_patterns=None, lib_patterns=None, exe_patterns=None
        #        2Proposal: Declare the patterns in the layout too?
        for include in self.build_includedirs:
            self._conan_file.copy("*.h", dst=self.pkg_includedir, src=include, keep_path=False)

        self._conan_file.copy("*.lib", dst=self.pkg_libdir,
                              src=self.build_lib_folder, keep_path=False)
        self._conan_file.copy("*.dll", dst=self.pkg_bindir,
                              src=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.exe", dst=self.pkg_bindir,
                              src=self.build_bin_folder, keep_path=False)

        self._conan_file.copy("*.so", dst=self.pkg_bindir,
                              src=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.so.*", dst=self.pkg_bindir,
                              src=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.a", dst=self.pkg_libdir,
                              src=self.build_lib_folder, keep_path=False)

    def imports(self):
        # FIXME: Not very flexible. Useless?
        #        Good enough for default?
        self._conan_file.copy("*.dll", dst=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.dylib", dst=self.build_lib_folder, keep_path=False)
        self._conan_file.copy("*.so", dst=self.build_lib_folder, keep_path=False)

    def package_info(self):
        # Make sure the ``package()`` and ``cpp_info`` are consistent
        self._conan_file.cpp_info.includedirs = self.pkg_includedir
        self._conan_file.cpp_info.libdirs = [self.pkg_libdir]
        self._conan_file.cpp_info.bindirs = [self.pkg_bindir]
        self._conan_file.cpp_info.buildirs = [self.pkg_builddir]


class CMakeLayout(Layout):
    def __init__(self, conanfile):
        super(CMakeLayout, self).__init__(conanfile)
        # Only input to build is the source directory, include not a thing here
        # relative to conanfile
        # FIXME: "src" is not true in most caseses, the CMakeList.txt is typically in the root
        self.src = ""
        # Output of build, relative to conanfile
        self.build = "build"
        # Output of build, relative to self.build_folder
        build_type = conanfile.settings.build_type
        if conanfile.settings.compiler == "Visual Studio":
            self.build_libdir = str(build_type)
            self.build_bindir = str(build_type)
            # self.installdir = os.path.join(self.build, str(build_type))
        else:
            self.build_libdir = ""
            self.build_bindir = ""


class CLionLayout(Layout):

    def __init__(self, conanfile):
        super(CLionLayout, self).__init__(conanfile)
        self.src = ""
        self.build = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
        self.build_libdir = ""  # If removed output dirs in conan basic setup
        self.build_bindir = ""
        self.build_includedirs = [self.build, ""]
