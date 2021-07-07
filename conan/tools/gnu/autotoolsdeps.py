from conan.tools.env import Environment
from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.errors import ConanException
from conans.model.new_build_info import NewCppInfo


class AutotoolsDeps:
    def __init__(self, conanfile):
        # Set the generic objects before mapping to env vars to let the user
        # alter some value
        self._conanfile = conanfile
        self._cpp_info = None
        self._cached_flags = False
        self._libs_flags = None
        self._cpp_flags = None
        self._ld_flags = None
        self._cxx_flags = None
        self._c_flags = None

        self._env = None

    @property
    def cpp_info(self):
        # The user can modify the cpp_info object before accessing the flags or the environment
        if self._cpp_info is None:
            self._cpp_info = NewCppInfo()
            for dep in self._conanfile.dependencies.host.values():
                dep_cppinfo = dep.new_cpp_info.copy()
                dep_cppinfo.set_relative_base_folder(dep.package_folder)
                # In case we have components, aggregate them, we do not support isolated
                # "targets" with autotools
                dep_cppinfo.aggregate_components()
                self._cpp_info.merge(dep_cppinfo)
        elif self._cached_flags is not None:
            raise ConanException("Error in AutotoolsDeps: You cannot access '.cpp_info' once"
                                 " the flags have been calculated")
        return self._cpp_info

    def _check_env_already_calculated(self):
        if self._env is not None:
            raise ConanException("Error in AutotoolsDeps: You cannot access the flags once"
                                 " the environment has been calculated")

    @property
    def _flags(self):
        if not self._cached_flags:
            # avoid the raise check if already calculated
            cpp_info = self._cpp_info or self.cpp_info
            self._cached_flags = GnuDepsFlags(self._conanfile, cpp_info)
        return self._cached_flags

    @property
    def libs_flags(self):
        self._check_env_already_calculated()
        if self._libs_flags is None:
            self._libs_flags = self._flags.libs
        return self._libs_flags

    @property
    def cpp_flags(self):
        self._check_env_already_calculated()
        if self._cpp_flags is None:
            self._cpp_flags = []
            self._cpp_flags.extend(self._flags.include_paths)
            self._cpp_flags.extend(self._flags.defines)
        return self._cpp_flags

    @property
    def cxx_flags(self):
        self._check_env_already_calculated()
        if self._cxx_flags is None:
            self._cxx_flags = self._flags.cxxflags
            if self._flags.sysroot:
                self._cxx_flags.append(self._flags.sysroot)
        return self._cxx_flags

    @property
    def c_flags(self):
        self._check_env_already_calculated()
        if self._c_flags is None:
            self._c_flags = self._flags.cflags
            if self._flags.sysroot:
                self._c_flags.append(self._flags.sysroot)
        return self._c_flags

    @property
    def ld_flags(self):
        self._check_env_already_calculated()
        if self._ld_flags is None:
            self._ld_flags = self._flags.sharedlinkflags
            self._ld_flags.extend(self._flags.exelinkflags)
            self._ld_flags.extend(self._flags.frameworks)
            self._ld_flags.extend(self._flags.framework_paths)
            self._ld_flags.extend(self._flags.lib_paths)
            # FIXME: Previously we had an argument "include_rpath_flags" defaulted to False
            self._ld_flags.extend(self._flags.rpath_flags)
            if self._flags.sysroot:
                self._ld_flags.append(self._flags.sysroot)
        return self._ld_flags

    @property
    def environment(self):
        if not self._env:
            env = Environment(self._conanfile)
            env.append("CPPFLAGS", self._cpp_flags or self.cpp_flags)
            env.append("LIBS", self._libs_flags or self.libs_flags)
            env.append("LDFLAGS", self._ld_flags or self.ld_flags)
            env.append("CXXFLAGS", self._cxx_flags or self.cxx_flags)
            env.append("CFLAGS", self._c_flags or self.c_flags)
            self._env = env
        return self._env

    def generate(self, auto_activate=True):
        self.environment.save_script("conanautotoolsdeps", auto_activate=auto_activate)
