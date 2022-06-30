from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.env import Environment
from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.model.new_build_info import NewCppInfo


def _get_cpp_info(deps):
    ret = NewCppInfo()
    for dep in deps:
        dep_cppinfo = dep.cpp_info.aggregated_components()
        # In case we have components, aggregate them, we do not support isolated
        # "targets" with autotools
        ret.merge(dep_cppinfo)
    return ret


def _rpaths_flags(deps):
    flags = []
    for dep in deps:
        flags.extend(["-Wl,-rpath -Wl,{}".format(libdir) for libdir in dep.cpp_info.libdirs
                      if dep.options.get_safe("shared", False)])
    return flags


def ordered_deps(conanfile):
    deps = conanfile.dependencies.host.topological_sort
    return[dep for dep in reversed(deps.values())]


def get_gnu_deps_flags(conanfile):
    """
    Given a ConanFile object, this function returns all the GNU flags from all the
    dependencies.

    :param conanfile: The current recipe object. Always use ``self``.
    :return: ``tuple`` of all the GNU flags.
    """
    deps = ordered_deps(conanfile)
    flags = GnuDepsFlags(conanfile, _get_cpp_info(deps))

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

    # set the rpath in Macos so that the library are found in the configure step
    if conanfile.settings.get_safe("os") == "Macos":
        ldflags.extend(_rpaths_flags(deps))

    # libs
    libs = flags.libs
    libs.extend(flags.system_libs)

    # cflags
    cflags = flags.cflags
    cxxflags = flags.cxxflags
    return cflags, cxxflags, cpp_flags, libs, ldflags


class AutotoolsDeps:
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._environment = None
        check_using_build_profile(self._conanfile)

    @property
    def environment(self):
        # TODO: Seems we want to make this uniform, equal to other generators
        if self._environment is None:
            # Get all the GNU flags from all the dependencies
            cflags, cxxflags, cpp_flags, libs, ldflags = get_gnu_deps_flags(self._conanfile)
            # Create the environment
            env = Environment()
            env.append("CPPFLAGS", cpp_flags)
            env.append("LIBS", libs)
            env.append("LDFLAGS", ldflags)
            env.append("CXXFLAGS", cxxflags)
            env.append("CFLAGS", cflags)
            self._environment = env
        return self._environment

    def vars(self, scope="build"):
        return self.environment.vars(self._conanfile, scope=scope)

    def generate(self, scope="build"):
        self.vars(scope).save_script("conanautotoolsdeps")
