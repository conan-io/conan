import platform

from conan.tools.env import Environment


class VirtualEnv:
    """ captures the conanfile environment that is defined from its
    dependencies, and also from profiles
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._conanfile.virtualenv = False

    def build_environment(self):
        """ collects the buildtime information from dependencies. This is the typical use case
        of build_requires defining information for consumers
        """
        build_env = Environment()
        # Top priority: profile
        profile_env = self._conanfile.buildenv
        build_env.compose(profile_env)

        for require, build_require in self._conanfile.dependencies.build_requires.items():
            if require.direct:
                # higher priority, explicit buildenv_info
                if build_require.buildenv_info:
                    build_env.compose(build_require.buildenv_info)
            else:
                # Lower priority, the runenv of all transitive "requires" of the build requires
                if build_require.runenv_info:
                    build_env.compose(build_require.runenv_info)
            # Then the implicit
            build_env.compose(self._runenv_from_cpp_info(build_require.cpp_info))

        # Requires in host context can also bring some direct buildenv_info
        for require in self._conanfile.dependencies.host_requires.values():
            if require.buildenv_info:
                build_env.compose(require.buildenv_info)

        return build_env

    @staticmethod
    def _runenv_from_cpp_info(cpp_info):
        """ return an Environment deducing the runtime information from a cpp_info
        """
        dyn_runenv = Environment()
        if cpp_info is None:  # This happens when the dependency is a private one = BINARY_SKIP
            return dyn_runenv
        if cpp_info.bin_paths:  # cpp_info.exes is not defined yet
            dyn_runenv.prepend_path("PATH", cpp_info.bin_paths)
        # If it is a build_require this will be the build-os, otherwise it will be the host-os
        if cpp_info.lib_paths:
            dyn_runenv.prepend_path("LD_LIBRARY_PATH", cpp_info.lib_paths)
            dyn_runenv.prepend_path("DYLD_LIBRARY_PATH", cpp_info.lib_paths)
        if cpp_info.framework_paths:
            dyn_runenv.prepend_path("DYLD_FRAMEWORK_PATH", cpp_info.framework_paths)
        return dyn_runenv

    def run_environment(self):
        """ collects the runtime information from dependencies. For normal libraries should be
        very occasional
        """
        runenv = Environment()
        # FIXME: Missing profile info

        # Visitor, breadth-first
        for require in self._conanfile.dependencies.host_requires.values():
            if require.runenv_info:
                runenv.compose(require.runenv_info)
            runenv.compose(self._runenv_from_cpp_info(require.cpp_info))

        return runenv

    def generate(self):
        build_env = self.build_environment()
        run_env = self.run_environment()
        # FIXME: Use settings, not platform Not always defined :(
        # os_ = self._conanfile.settings_build.get_safe("os")
        if build_env:  # Only if there is something defined
            if platform.system() == "Windows":
                build_env.save_bat("conanbuildenv.bat")
            else:
                build_env.save_sh("conanbuildenv.sh")
        if run_env:
            if platform.system() == "Windows":
                run_env.save_bat("conanrunenv.bat")
            else:
                run_env.save_sh("conanrunenv.sh")
