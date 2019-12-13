import os


class Layout(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

        # build time layout
        self.src = ""  # relative to source_folder
        self.build = "build"  # relative to build_folder
        self.includedirs = [""]  # relative to build_folder (and source_folder) in the cache
        # TODO: To be able to declare an includedir in case we have headers in build and src
        #       but enabling the override of the build by command line we would need to do
        #       something like: `includedirs = ["src", self.build]` but the value of self.build
        #       might be blocked if the "constructor" provided another one

        # Where the libs and dll's are, relative to build_folder.${self.build}. Default self.build
        self._build_libdir = None
        self._build_bindir = None

        # Where to put install files: lock-files, etc relative to install_folder
        self._installdir = None

        # package layout
        self.libdir = "lib"
        self.bindir = "bin"
        self.includedir = "include"
        self.builddir = "build"

    @property
    def installdir(self):
        return self._installdir or self.build

    @installdir.setter
    def installdir(self, v):
        self._installdir = v

    @property
    def build_libdir(self):
        return os.path.join(self.build, self._build_libdir) if self._build_libdir is not None else self.build

    @build_libdir.setter
    def build_libdir(self, v):
        self._build_libdir = v

    @property
    def build_bindir(self):
        return os.path.join(self.build, self._build_bindir) if self._build_bindir is not None else self.build

    @build_bindir.setter
    def build_bindir(self, v):
        self._build_bindir = v

    @property
    def install_folder(self):
        return os.path.join(self._conanfile.install_folder, self.installdir)

    @property
    def build_folder(self):
        return os.path.join(self._conanfile.build_folder, self.build)

    @property
    def source_folder(self):
        return os.path.join(self._conanfile.source_folder, self.src)

    def package(self):
        # FIXME: Not very flexible. Useless? What if I want to copy only some patterns
        #        Good enough for default?
        for include in self.includedirs:
            self._conanfile.copy("*.h", dst=self.includedir, src=include, keep_path=False)

        self._conanfile.copy("*.lib", dst=self.libdir, src=self.build_libdir, keep_path=False)
        self._conanfile.copy("*.dll", dst=self.bindir, src=self.build_bindir, keep_path=False)
        self._conanfile.copy("*.exe", dst=self.bindir, src=self.build_bindir, keep_path=False)

        self._conanfile.copy("*.so", dst=self.bindir, src=self.build_bindir, keep_path=False)
        self._conanfile.copy("*.so.*", dst=self.bindir, src=self.build_bindir, keep_path=False)
        self._conanfile.copy("*.a", dst=self.libdir, src=self.build_libdir, keep_path=False)

    def imports(self):
        # FIXME: Not very flexible. Useless?
        #        Good enough for default?
        self._conanfile.copy("*.dll", dst=self.build_bindir, keep_path=False)
        self._conanfile.copy("*.dylib", dst=self.build_libdir, keep_path=False)
        self._conanfile.copy("*.so", dst=self.build_libdir, keep_path=False)

    def package_info(self):
        # Make sure the ``package()`` and ``cpp_info`` are consistent
        self._conanfile.cpp_info.includedirs = [self.includedir]
        self._conanfile.cpp_info.libdirs = [self.libdir]
        self._conanfile.cpp_info.bindirs = [self.bindir]
        self._conanfile.cpp_info.buildris = [self.builddir]


class CMakeLayout(Layout):
    def __init__(self, conanfile):
        super(CMakeLayout, self).__init__(conanfile)
        # Only input to build is the source directory, include not a thing here
        # relative to conanfile
        self.src = "src"
        # Output of build, relative to conanfile
        self.includedirs = ["src"]
        # Output of build, relative to self.build_folder
        build_type = self._conanfile.settings.build_type
        if self._conanfile.settings.compiler == "Visual Studio":
            self.build_libdir = os.path.join(self.build, str(build_type))
            self.build_bindir = os.path.join(self.build, str(build_type))
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
        self.includedirs = [self.build]
