import os


class _BuildLayout(object):

    def __init__(self):
        self.folder = "build"
        self.src_folder = ""
        # TODO: To discuss, are we sure we want only 1 value?
        self.libdir = ""  # Relative to self.folder
        # TODO: To discuss, are we sure we want only 1 value?
        self.bindir = ""  # Relative to self.folder
        self.includedirs = [""]  # Relative to self.folder (and or self.src_folder)
        self.installdir = None  # Not relative to self.folder


class _PackageLayout(object):

    def __init__(self):
        # package layout
        # TODO: To discuss, are we sure we want only 1 value?
        self.libdir = "lib"
        self.bindir = "bin"
        self.includedir = "include"
        self.builddir = "build"


class Layout(object):
    def __init__(self, conan_file):
        self._conan_file = conan_file
        self.build = _BuildLayout()
        self.package = _PackageLayout()

    @property
    def install_folder(self):
        installdir = self.build.installdir if self.build.installdir is not None \
            else self.build.folder
        return os.path.join(self._conan_file.install_folder, installdir)

    @property
    def build_folder(self):
        return os.path.join(self._conan_file.build_folder, self.build.folder)

    @property
    def build_lib_folder(self):
        return os.path.join(self._conan_file.build_folder, self.build.folder, self.build.libdir)

    @property
    def build_bin_folder(self):
        return os.path.join(self._conan_file.build_folder, self.build.folder, self.build.bindir)

    @property
    def source_folder(self):
        return os.path.join(self._conan_file.source_folder, self.build.src_folder)

    def package(self):
        # FIXME: Not very flexible. Useless? What if I want to copy only some patterns
        #        Good enough for default?
        #        Proposal kwargs: header_patterns=None, lib_patterns=None, exe_patterns=None
        for include in self.build.includedirs:
            self._conan_file.copy("*.h", dst=self.package.includedir, src=include, keep_path=False)

        self._conan_file.copy("*.lib", dst=self.package.libdir,
                              src=self.build_lib_folder, keep_path=False)
        self._conan_file.copy("*.dll", dst=self.package.bindir,
                              src=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.exe", dst=self.package.bindir,
                              src=self.build_bin_folder, keep_path=False)

        self._conan_file.copy("*.so", dst=self.package.bindir,
                              src=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.so.*", dst=self.package.bindir,
                              src=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.a", dst=self.package.libdir,
                              src=self.build_lib_folder, keep_path=False)

    def imports(self):
        # FIXME: Not very flexible. Useless?
        #        Good enough for default?
        self._conan_file.copy("*.dll", dst=self.build_bin_folder, keep_path=False)
        self._conan_file.copy("*.dylib", dst=self.build_lib_folder, keep_path=False)
        self._conan_file.copy("*.so", dst=self.build_lib_folder, keep_path=False)

    def package_info(self):
        # Make sure the ``package()`` and ``cpp_info`` are consistent
        self._conan_file.cpp_info.includedirs = self.package.includedir
        self._conan_file.cpp_info.libdirs = [self.package.libdir]
        self._conan_file.cpp_info.bindirs = [self.package.bindir]
        self._conan_file.cpp_info.buildirs = [self.package.builddir]


class CMakeLayout(Layout):
    def __init__(self, conanfile):
        super(CMakeLayout, self).__init__(conanfile)
        # Only input to build is the source directory, include not a thing here
        # relative to conanfile
        # FIXME: This is not true many times, the CMakeList.txt is typically in the root
        self.build.src_folder = "src"
        # Output of build, relative to conanfile
        self.build.includedirs = ["src"]
        # Output of build, relative to self.build_folder
        build_type = conanfile.settings.build_type
        if conanfile.settings.compiler == "Visual Studio":
            self.build.libdir = str(build_type)
            self.build.bindir = str(build_type)
            # self.installdir = os.path.join(self.build, str(build_type))
        else:
            self.build_libdir = ""
            self.build_bindir = ""


class CLionLayout(Layout):

    def __init__(self, conanfile):
        super(CLionLayout, self).__init__(conanfile)
        self.build.src_folder = ""
        self.build.folder = "cmake-build-{}".format(str(conanfile.settings.build_type).lower())
        self.build.libdir = ""  # If removed output dirs in conan basic setup
        self.build.bindir = ""
        self.build.includedirs = [self.build.folder, ""]
