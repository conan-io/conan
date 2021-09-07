from conan.tools.env import Environment
from conan.tools.env.virtualrunenv import runenv_from_cpp_info


class VirtualBuildEnv:
    """ captures the conanfile environment that is defined from its
    dependencies, and also from profiles
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._conanfile.virtualenv = False

    def environment(self):
        """ collects the buildtime information from dependencies. This is the typical use case
        of build_requires defining information for consumers
        """
        # FIXME: Cache value?
        build_env = Environment(self._conanfile)

        # Top priority: profile
        profile_env = self._conanfile.buildenv
        build_env.compose_env(profile_env)

        build_requires = self._conanfile.dependencies.build.topological_sort
        for require, build_require in reversed(build_requires.items()):
            if require.direct:  # Only buildenv_info from direct deps is propagated
                # higher priority, explicit buildenv_info
                if build_require.buildenv_info:
                    build_env.compose_env(build_require.buildenv_info)
            # Lower priority, the runenv of all transitive "requires" of the build requires
            if build_require.runenv_info:
                build_env.compose_env(build_require.runenv_info)
            # Then the implicit
            build_env.compose_env(runenv_from_cpp_info(self._conanfile, build_require.cpp_info))

        # Requires in host context can also bring some direct buildenv_info
        host_requires = self._conanfile.dependencies.host.topological_sort
        for require in reversed(host_requires.values()):
            if require.buildenv_info:
                build_env.compose_env(require.buildenv_info)

        return build_env

    def generate(self, auto_activate=True):
        build_env = self.environment()
        if build_env:  # Only if there is something defined
            build_env.save_script("conanbuildenv", auto_activate=auto_activate)
