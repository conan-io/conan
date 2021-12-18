from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.env import Environment
from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.model.new_build_info import NewCppInfo


class AutotoolsDeps:
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._environment = None
        check_using_build_profile(self._conanfile)

    def _get_cpp_info(self):
        ret = NewCppInfo()
        for dep in self._conanfile.dependencies.host.values():
            dep_cppinfo = dep.cpp_info.aggregated_components()
            dep_cppinfo.set_relative_base_folder(dep.package_folder)
            # In case we have components, aggregate them, we do not support isolated
            # "targets" with autotools
            ret.merge(dep_cppinfo)
        return ret

    @property
    def environment(self):
        # TODO: Seems we want to make this uniform, equal to other generators
        if self._environment is None:
            flags = GnuDepsFlags(self._conanfile, self._get_cpp_info())

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
            self._environment = env
        return self._environment

    def vars(self, scope="build"):
        return self.environment.vars(self._conanfile, scope=scope)

    def generate(self,  scope="build"):
        self.vars(scope).save_script("conanautotoolsdeps")
