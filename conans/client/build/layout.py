import os


class Layout(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        # build time layout, relative to conanfile
        self.src = ""
        self.build = "build"
        self.includedirs = [""]
        # Where the libs and dlls are, relative to conanfile
        self.build_libdir = ""
        self.build_bindir = ""
        # Where to put install files: lockfiles, etc
        self.installdir = ""
        # package layout
        self.libdir = "lib"
        self.bindir = "bin"
        self.includedir = "include"
        self.builddir = "build"

    def package(self):
        for include in self.includedirs:
            self._conanfile.copy("*.h", dst=self.includedir, src=include)

        self._conanfile.copy("*.lib", dst=self.libdir, src=self.build_libdir)
        self._conanfile.copy("*.dll", dst=self.bindir, src=self.build_bindir)
        self._conanfile.copy("*.exe", dst=self.bindir, src=self.build_bindir)

        self._conanfile.copy("*.so", dst=self.bindir, src=self.build_bindir)
        self._conanfile.copy("*.so.*", dst=self.bindir, src=self.build_bindir)
        self._conanfile.copy("*.a", dst=self.libdir, src=self.build_libdir)

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
            self.installdir = os.path.join(self.build, str(build_type))
        else:
            self.build_libdir = ""
            self.build_bindir = ""
