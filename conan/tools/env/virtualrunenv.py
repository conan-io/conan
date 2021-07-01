from conan.tools.env import Environment
from conan.tools.env.environment import save_script


def runenv_from_cpp_info(cpp_info):
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


class VirtualRunEnv:
    """ captures the conanfile environment that is defined from its
    dependencies, and also from profiles
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile

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
                runenv.compose(dep.runenv_info)
            runenv.compose(runenv_from_cpp_info(dep.cpp_info))

        return runenv

    def generate(self, auto_activate=False):
        run_env = self.environment()
        if run_env:
            save_script(self._conanfile, run_env, "conanrunenv", auto_activate=auto_activate)

