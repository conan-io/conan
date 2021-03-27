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
        # Top priority: profile
        profile_env = self._conanfile.buildenv
        build_env.compose(profile_env)

        # First visit the direct build_requires
        transitive_requires = []
        for build_require in self._conanfile.dependencies.build_requires:
            # higher priority, explicit buildenv_info
            if build_require.buildenv_info:
                build_env.compose(build_require.buildenv_info)
            # Second, the implicit self information in build_require.cpp_info
            build_env.compose(self._runenv_from_cpp_info(build_require.cpp_info))
            # Lower priority, the runenv of all transitive "requires" of the build requires
            for require in build_require.dependencies.requires:
                if require not in transitive_requires:
                    transitive_requires.append(require)

        self._apply_transitive_runenv(transitive_requires, build_env)

        # Requires in host context can also bring some direct buildenv_info
        def _apply_transitive_buildenv(reqs, env):
            all_requires = []
            while reqs:
                new_requires = []
                for r in reqs:
                    # The explicit has more priority
                    if r.buildenv_info:
                        env.compose(r.buildenv_info)
                    for transitive in r.dependencies.requires:
                        # Avoid duplication/repetitions
                        if transitive not in new_requires and transitive not in all_requires:
                            new_requires.append(transitive)
                reqs = new_requires

        _apply_transitive_buildenv(self._conanfile.dependencies.requires, build_env)

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

    def _apply_transitive_runenv(self, next_requires, runenv):
        all_requires = []
        while next_requires:
            new_requires = []
            for require in next_requires:
                # The explicit has more priority
                if require.runenv_info:
                    runenv.compose(require.runenv_info)
                # Then the implicit
                runenv.compose(self._runenv_from_cpp_info(require.cpp_info))
                all_requires.append(require)

                for transitive in require.dependencies.requires:
                    # Avoid duplication/repetitions
                    if transitive not in new_requires and transitive not in all_requires:
                        new_requires.append(transitive)
            next_requires = new_requires

    def run_environment(self):
        """ collects the runtime information from dependencies. For normal libraries should be
        very occasional
        """
        runenv = Environment()
        # FIXME: Missing profile info

        # Visitor, breadth-first
        self._apply_transitive_runenv(self._conanfile.dependencies.requires, runenv)
        # At the moment we are adding "test-requires" (build_requires in host context)
        # to the "runenv", but this will be investigated
        host_build_requires = [br for br in self._conanfile.dependencies.build_requires
                               if br.context == CONTEXT_HOST]
        self._apply_transitive_runenv(host_build_requires, runenv)

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
