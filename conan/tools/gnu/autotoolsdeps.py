from conan.tools.env import Environment
from conans.model.build_info import DepCppInfo


class AutotoolsDeps:
    def __init__(self, conanfile):
        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self._conanfile = conanfile

        self.libs = []
        self.system_libs = []
        self.include_paths = []
        self.lib_paths = []
        self.defines = []
        self.cflags = []
        self.cxxflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self.frameworks = []
        self.framework_paths = []
        self.sysroot = None

        def merge_lists(seq1, seq2):
            return [s for s in seq1 if s not in seq2] + seq2

        def merge(dep):
            dep_cpp_info = DepCppInfo(dep.cpp_info)  # To deal with components
            self.system_libs = merge_lists(self.system_libs, dep_cpp_info.system_libs)
            self.include_paths = merge_lists(self.include_paths, dep_cpp_info.include_paths)
            self.lib_paths = merge_lists(self.lib_paths, dep_cpp_info.lib_paths)
            self.framework_paths = merge_lists(self.framework_paths, dep_cpp_info.framework_paths)
            self.libs = merge_lists(self.libs, dep_cpp_info.libs)
            self.frameworks = merge_lists(self.frameworks, dep_cpp_info.frameworks)

            # Note these are in reverse order
            self.defines = merge_lists(dep_cpp_info.defines, self.defines)
            self.cxxflags = merge_lists(dep_cpp_info.cxxflags, self.cxxflags)
            self.cflags = merge_lists(dep_cpp_info.cflags, self.cflags)
            self.sharedlinkflags = merge_lists(dep_cpp_info.sharedlinkflags, self.sharedlinkflags)
            self.exelinkflags = merge_lists(dep_cpp_info.exelinkflags, self.exelinkflags)

            if not self.sysroot:
                self.sysroot = dep_cpp_info.sysroot

        def _apply_transitive_runenv(next_requires):
            # TODO: This visitor is same as VirtualEnv runenv_info one, extract
            all_requires = []
            while next_requires:
                new_requires = []
                for require in next_requires:
                    # The explicit has more priority
                    merge(require)
                    all_requires.append(require)

                    for transitive in require.dependencies.requires:
                        # Avoid duplication/repetitions
                        if transitive not in new_requires and transitive not in all_requires:
                            new_requires.append(transitive)
                next_requires = new_requires

        _apply_transitive_runenv(self._conanfile.dependencies.requires)

    def environment(self):
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
        frameworks_paths = ["-F %s" % framework_path for framework_path in self.framework_paths]
        ldflags = self.sharedlinkflags
        ldflags.extend(self.exelinkflags)
        ldflags.extend(frameworks)
        ldflags.extend(frameworks_paths)
        lib_paths = ['-L"%s"' % p for p in self.lib_paths]
        ldflags.extend(lib_paths)

        # cflags
        cflags = self.cflags
        cxxflags = self.cxxflags

        if self.sysroot:
            srf = '--sysroot={}'.format(self.sysroot)
            cflags.append(srf)
            cxxflags.append(srf)
            ldflags.append(srf)

        env = Environment()
        env.append("CPPFLAGS", cpp_flags)
        env.append("LIBS", libs)
        env.append("LDFLAGS", ldflags)
        env.append("CXXFLAGS", cxxflags)
        env.append("CFLAGS", cflags)
        return env

    def generate(self):
        env = self.environment()
        env.save_sh("conanautotoolsdeps.sh")
        env.save_bat("conanautotoolsdeps.bat")
