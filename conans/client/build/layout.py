import os


class Layout(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

        # build time layout
        self.src = ""  # relative to source_folder
        self.build = "build"  # relative to build_folder
        self.includedirs = [""]  # relative to build_folder??? to both??

        # Where the libs and dlls are, relative to build_folder
        self._build_libdir = None
        self._build_bindir = None

        # Where to put install files: lockfiles, etc relative to install_folder
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
        return self._build_libdir or self.build

    @build_libdir.setter
    def build_libdir(self, v):
        self._build_libdir = v

    @property
    def build_bindir(self):
        return self._build_bindir or self.build

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
        self._conanfile.copy("*.a", dst=self.build_bindir, keep_path=False)  # FIXME: Remove this
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
