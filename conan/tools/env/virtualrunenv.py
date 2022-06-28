import os

from conan.tools.env import Environment


def runenv_from_cpp_info(conanfile, dep, os_name):
    """ return an Environment deducing the runtime information from a cpp_info
    """
    # FIXME: Remove conanfile arg
    dyn_runenv = Environment()

    cpp_info = dep.cpp_info.aggregated_components()

    def _prepend_path(envvar, paths):
        existing = [p for p in paths if os.path.exists(p)] if paths else None
        if existing:
            dyn_runenv.prepend_path(envvar, existing)

    _prepend_path("PATH", cpp_info.bindirs)
    # If it is a build_require this will be the build-os, otherwise it will be the host-os
    if os_name and not os_name.startswith("Windows"):
        _prepend_path("LD_LIBRARY_PATH", cpp_info.libdirs)
        _prepend_path("DYLD_LIBRARY_PATH", cpp_info.libdirs)
        _prepend_path("DYLD_FRAMEWORK_PATH", cpp_info.frameworkdirs)
    return dyn_runenv


class VirtualRunEnv:
    """ captures the conanfile environment that is defined from its
    dependencies, and also from profiles
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._conanfile.virtualrunenv = False
        self.basename = "conanrunenv"
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
            f += "-" + self.configuration
        if self.arch:
            f += "-" + self.arch
        return f

    def environment(self):
        """ collects the runtime information from dependencies. For normal libraries should be
        very occasional
        """
        runenv = Environment()
        # FIXME: Missing profile info
        # FIXME: Cache value?

        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        for _, dep in list(host_req.items()) + list(test_req.items()):
            if dep.runenv_info:
                runenv.compose_env(dep.runenv_info)
            runenv.compose_env(runenv_from_cpp_info(self._conanfile, dep,
                                                    self._conanfile.settings.get_safe("os")))

        return runenv

    def vars(self, scope="run"):
        return self.environment().vars(self._conanfile, scope=scope)

    def generate(self, scope="run"):
        run_env = self.environment()
        run_env.vars(self._conanfile, scope=scope).save_script(self._filename)
