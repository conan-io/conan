from conan.tools.env import Environment
from conan.tools.gnu.autotoolsdeps_flags import AutoToolsDepsFlags
from conans.model.new_build_info import NewCppInfo


class AutotoolsDeps:
    def __init__(self, conanfile):
        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self._conanfile = conanfile
        self._cpp_info = None

    @property
    def cpp_info(self):
        if self._cpp_info is None:
            self._cpp_info = NewCppInfo()
            for dep in self._conanfile.dependencies.host.values():
                dep_cppinfo = dep.new_cpp_info.copy()
                dep_cppinfo.set_relative_base_folder(dep.package_folder)
                # In case we have components, aggregate them, we do not support isolated
                # "targets" with autotools
                dep_cppinfo.aggregate_components()
                self._cpp_info.merge(dep_cppinfo)
        return self._cpp_info

    def environment(self):
        flags = AutoToolsDepsFlags(self._conanfile, self.cpp_info)

        # cpp_flags
        cpp_flags = []
        cpp_flags.extend(flags.include_paths)
        cpp_flags.extend(flags.defines)

        # Ldflags
        ldflags = flags.sharedlinkflags
        ldflags.extend(flags.exelinkflags)
        ldflags.extend(flags.frameworks)
        ldflags.extend(flags.framework_paths)
        ldflags.extend(flags.lib_paths)
        # FIXME: Previously we had an argument "include_rpath_flags" defaulted to False
        ldflags.extend(flags.rpath_flags)

        # cflags
        cflags = flags.cflags
        cxxflags = flags.cxxflags

        srf = flags.sysroot
        if srf:
            cflags.append(srf)
            cxxflags.append(srf)
            ldflags.append(srf)

        env = Environment()
        env.append("CPPFLAGS", cpp_flags)
        env.append("LIBS", flags.libs)
        env.append("LDFLAGS", ldflags)
        env.append("CXXFLAGS", cxxflags)
        env.append("CFLAGS", cflags)
        return env

    def generate(self, env=None):
        env = env or self.environment()
        env.save_script("conanautotoolsdeps")
