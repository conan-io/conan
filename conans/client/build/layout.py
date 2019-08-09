import os


class Layout(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.src = ""
        # Relative build folder
        self.build = "build"
        self.includedirs = [""]
        self.libdir = ""
        self.bindir = ""

    def package(self):
        for include in self.includedirs:
            self._conanfile.copy("*.h", dst="include", src=include)
        self._conanfile.copy("*.lib", dst="lib", src=str(self.libdir))
        self._conanfile.copy("*.a", dst="lib", src=str(self.libdir))
        self._conanfile.copy("*.exe", dst="bin", src=str(self.bindir))

    @property
    def lib_path(self):
        return os.path.join(self.build, str(self.libdir))


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
            self.libdir = build_type
            self.bindir = build_type
        else:
            self.libdir = ""
            self.bindir = ""
