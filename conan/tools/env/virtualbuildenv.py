from conan.internal import check_duplicated_generator
from conan.tools.env import Environment
from conan.tools.env.virtualrunenv import runenv_from_cpp_info


class VirtualBuildEnv:
    """ Calculates the environment variables of the build time context and produces a conanbuildenv
        .bat or .sh script
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._conanfile.virtualbuildenv = False
        self.basename = "conanbuildenv"
        # TODO: Make this use the settings_build
        self.configuration = conanfile.settings.get_safe("build_type")
        if self.configuration:
            self.configuration = self.configuration.lower()
        self.arch = conanfile.settings.get_safe("arch")
        if self.arch:
            self.arch = self.arch.lower()

    @property
    def _filename(self):
        f = self.basename
        if self.configuration:
            f += "-" + self.configuration.replace(".", "_")
        if self.arch:
            f += "-" + self.arch.replace(".", "_")
        return f

    def environment(self):
        """
        Returns an ``Environment`` object containing the environment variables of the build context.

        :return: an ``Environment`` object instance containing the obtained variables.
        """
        # FIXME: Cache value?
        build_env = Environment()

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
            if hasattr(self._conanfile, "settings_build"):
                os_name = self._conanfile.settings_build.get_safe("os")
            else:
                os_name = self._conanfile.settings.get_safe("os")
            build_env.compose_env(runenv_from_cpp_info(build_require, os_name))

        # Requires in host context can also bring some direct buildenv_info
        host_requires = self._conanfile.dependencies.host.topological_sort
        for require in reversed(host_requires.values()):
            if require.buildenv_info:
                build_env.compose_env(require.buildenv_info)

        return build_env

    def vars(self, scope="build"):
        """
        :param scope: Scope to be used.
        :return: An ``EnvVars`` instance containing the computed environment variables.
        """
        return self.environment().vars(self._conanfile, scope=scope)

    def generate(self, scope="build"):
        """
        Produces the launcher scripts activating the variables for the build context.

        :param scope: Scope to be used.
        """
        check_duplicated_generator(self, self._conanfile)
        build_env = self.environment()
        build_env.vars(self._conanfile, scope=scope).save_script(self._filename)
