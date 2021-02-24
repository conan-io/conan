import platform

from conan.tools.env import Environment
from conans.client.graph.graph import CONTEXT_BUILD


class VirtualEnv:
    """ captures the conanfile environment that is defined from its
    dependencies, and also from profiles
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def build_environment(self):
        """ collects the buildtime information from dependencies. This is the typical use case
        of build_requires defining information for consumers
        """
        # Visit all dependencies
        deps_env = Environment()
        # TODO: The visitor of dependencies needs to be implemented correctly
        # TODO: The environment should probably be composed with direct dependencies first
        # TODO: in paths, but this is the opposite
        for dep in self._conanfile.dependencies.all:
            # environ_info is always "build"
            dep_env = dep.buildenv_info
            if dep_env is not None:
                deps_env.compose(dep_env)
            if dep.context == CONTEXT_BUILD:
                runenv = self._runenv_from_cpp_info(dep)
                deps_env.compose(runenv)

        # The profile environment has precedence, applied last
        profile_env = self._conanfile.buildenv
        deps_env.compose(profile_env)
        return deps_env

    def autorun_environment(self):
        """ automatically collects the runtime environment from 'cpp_info' from dependencies
        By default is enabled and will be captured in 'runenv.xxx' but maybe can be disabled
        by parameter or [conf]
        """
        dyn_runenv = Environment()
        for dep in self._conanfile.dependencies.all:
            if dep.context == CONTEXT_BUILD:  # Build environment cannot happen in runtime
                continue
            env = self._runenv_from_cpp_info(dep)
            dyn_runenv.compose(env)
        return dyn_runenv

    @staticmethod
    def _runenv_from_cpp_info(conanfile_dep):
        """ return an Environment deducing the runtime information from a cpp_info
        """
        dyn_runenv = Environment()
        cpp_info = conanfile_dep.cpp_info
        if cpp_info.exes:
            dyn_runenv.prepend_path("PATH", cpp_info.bin_paths)
        # If it is a build_require this will be the build-os, otherwise it will be the host-os
        os_ = conanfile_dep.settings.get_safe("os")
        if cpp_info.lib_paths:
            if os_ == "Linux":
                dyn_runenv.prepend_path("LD_LIBRARY_PATH", cpp_info.lib_paths)
            elif os_ == "Macos":
                dyn_runenv.prepend_path("DYLD_LIBRARY_PATH", cpp_info.lib_paths)
        if cpp_info.framework_paths:
            dyn_runenv.prepend_path("DYLD_FRAMEWORK_PATH", cpp_info.framework_paths)
        return dyn_runenv

    def run_environment(self):
        """ collects the runtime information from dependencies. For normal libraries should be
        very occasional
        """
        # Visit all dependencies
        deps_env = Environment()
        for dep in self._conanfile.dependencies.all:
            # run_environ_info is always "host"
            dep_env = dep.runenv_info
            if dep_env is not None:
                deps_env.compose(dep_env)

        autorun = self.autorun_environment()
        deps_env.compose(autorun)
        # FIXME: Missing profile info
        result = deps_env
        return result

    def generate(self):
        build_env = self.build_environment()
        run_env = self.run_environment()
        # FIXME: Use settings, not platform Not always defined :(
        # os_ = self._conanfile.settings_build.get_safe("os")
        if platform.system() == "Windows":
            build_env.save_bat("buildenv.bat")
            run_env.save_bat("runenv.bat")
        else:
            build_env.save_sh("buildenv.sh")
            run_env.save_sh("runenv.sh")
