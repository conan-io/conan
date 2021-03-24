import platform

from conan.tools.env import Environment
from conans.client.graph.graph import CONTEXT_HOST


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
        # First visit the direct build_requires
        for build_require in self._conanfile.dependencies.build_requires:
            # Lower priority, the runenv of all transitive "requires" of the build requires
            for require in build_require.dependencies.requires:
                build_env.compose(self._collect_transitive_runenv(require))
            # Second, the implicit self information in build_require.cpp_info
            build_env.compose(self._runenv_from_cpp_info(build_require.cpp_info))
            # Finally, higher priority, explicit buildenv_info
            if build_require.buildenv_info:
                build_env.compose(build_require.buildenv_info)

        # Requires in host context can also bring some direct buildenv_info
        def _collect_transitive_buildenv(d):
            r = Environment()
            for child in d.dependencies.requires:
                r.compose(_collect_transitive_buildenv(child))
            # Then the explicit self
            if d.buildenv_info:
                r.compose(d.buildenv_info)
            return r
        for require in self._conanfile.dependencies.requires:
            build_env.compose(_collect_transitive_buildenv(require))

        # The profile environment has precedence, applied last
        profile_env = self._conanfile.buildenv
        build_env.compose(profile_env)
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

    def _collect_transitive_runenv(self, d):
        r = Environment()
        for child in d.dependencies.requires:
            r.compose(self._collect_transitive_runenv(child))
        # Apply "d" runenv, first the implicit
        r.compose(self._runenv_from_cpp_info(d.cpp_info))
        # Then the explicit
        if d.runenv_info:
            r.compose(d.runenv_info)
        return r

    def run_environment(self):
        """ collects the runtime information from dependencies. For normal libraries should be
        very occasional
        """
        runenv = Environment()
        # At the moment we are adding "test-requires" (build_requires in host context)
        # to the "runenv", but this will be investigated
        for build_require in self._conanfile.dependencies.build_requires:
            if build_require.context == CONTEXT_HOST:
                runenv.compose(self._collect_transitive_runenv(build_require))
        for require in self._conanfile.dependencies.requires:
            runenv.compose(self._collect_transitive_runenv(require))

        # FIXME: Missing profile info
        result = runenv
        return result

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
