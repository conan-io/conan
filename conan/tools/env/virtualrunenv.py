import os

from conan.tools.env import Environment


def runenv_from_cpp_info(conanfile, dep, os_name):
    """ return an Environment deducing the runtime information from a cpp_info
    """
    # FIXME: Remove conanfile arg
    dyn_runenv = Environment()

    cpp_info = dep.cpp_info.aggregated_components()
    pkg_folder = dep.package_folder
    # FIXME: This code is dead, cpp_info cannot be None
    if cpp_info is None:  # This happens when the dependency is a private one = BINARY_SKIP
        return dyn_runenv

    def _handle_paths(paths):
        result = []
        for p in paths:
            abs_path = os.path.join(pkg_folder, p)
            if os.path.exists(abs_path):
                result.append(abs_path)
        return result

    if cpp_info.bindirs:  # cpp_info.exes is not defined yet
        dyn_runenv.prepend_path("PATH", _handle_paths(cpp_info.bindirs))
    # If it is a build_require this will be the build-os, otherwise it will be the host-os
    if os_name and not os_name.startswith("Windows"):
        if cpp_info.libdirs:
            libdirs = _handle_paths(cpp_info.libdirs)
            dyn_runenv.prepend_path("LD_LIBRARY_PATH", libdirs)
            dyn_runenv.prepend_path("DYLD_LIBRARY_PATH", libdirs)
        if cpp_info.frameworkdirs:
            dyn_runenv.prepend_path("DYLD_FRAMEWORK_PATH", _handle_paths(cpp_info.frameworkdirs))
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

    def vars(self, scope="build"):
        return self.environment().vars(self._conanfile, scope=scope)

    def generate(self, scope="run"):
        run_env = self.environment()
        if run_env:
            run_env.vars(self._conanfile, scope=scope).save_script(self._filename)
