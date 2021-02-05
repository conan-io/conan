from conan.tools.env import Environment


class AutotoolsDeps(object):
    def __init__(self, conanfile):
        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self._conanfile = conanfile
        deps_cpp_info = conanfile.deps_cpp_info
        self.libs = list(deps_cpp_info.libs)
        self.libs.extend(list(deps_cpp_info.system_libs))
        self.include_paths = list(deps_cpp_info.include_paths)
        self.library_paths = list(deps_cpp_info.lib_paths)
        self.defines = list(deps_cpp_info.defines)
        self.cflags = list(deps_cpp_info.cflags)
        self.cxx_flags = list(deps_cpp_info.cxxflags)
        self.sharedlinkflags = list(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = list(deps_cpp_info.exelinkflags)
        self.frameworks = list(deps_cpp_info.frameworks)
        self.frameworks_paths = list(deps_cpp_info.framework_paths)
        self.sysroot = deps_cpp_info.sysroot

    def generate(self):
        # cpp_flags
        cpp_flags = []
        include_paths = ['-I"%s"' % p for p in self.include_paths]
        cpp_flags.extend(include_paths)
        cpp_flags.extend(["-D%s" % define for define in self.defines])

        # Libs
        libs = ["-l%s" % library for library in self.libs]

        # Ldflags
        # TODO: Discuss, should the helper filter frameworks based on compiler?
        frameworks = ["-framework %s" % framework for framework in self.frameworks]
        frameworks_paths = ["-F %s" % framework_path for framework_path in self.frameworks_paths]
        ldflags = self.sharedlinkflags
        ldflags.extend(self.exelinkflags)
        ldflags.extend(frameworks)
        ldflags.extend(frameworks_paths)
        lib_paths = ['-L"%s"' % p for p in self.library_paths]
        ldflags.extend(lib_paths)

        # cflags
        cflags = []
        cxxflags = []

        if self.sysroot:
            srf = '--sysroot={}'.format(self.sysroot)
            cflags.append(srf)
            cxxflags.append(srf)
            ldflags.append(srf)

        env = Environment()
        env["CPPFLAGS"].append(cpp_flags)
        env["LIBS"].append(libs)
        env["LDFLAGS"].append(ldflags)
        env["CXXFLAGS"].append(cxxflags)
        env["CFLAGS"].append(cflags)

        env.save_sh("autotoolsdeps.sh")
        env.save_bat("autotoolsdeps.bat")
