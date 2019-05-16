

class RunEnvironment(object):
    """
    - PATH: pointing to the bin/ directories of the requires
    - LD_LIBRARY_PATH: requires lib_paths for Linux
    - DYLD_LIBRARY_PATH: requires lib_paths for OSx
    """
    def __init__(self, conanfile):
        """
        :param conanfile: ConanFile instance
        """
        self.conanfile = conanfile

    @property
    def vars(self):
        lib_paths = []
        bin_paths = []
        for dep in self.conanfile.deps_cpp_info.deps:
            lib_paths.extend(self.conanfile.deps_cpp_info[dep].lib_paths)
            bin_paths.extend(self.conanfile.deps_cpp_info[dep].bin_paths)

        python_paths = []
        for dep in self.conanfile.deps_env_info.deps:
            python_paths.extend(self.conanfile.deps_env_info[dep].vars.get('PYTHONPATH',[]))

        ret = {"DYLD_LIBRARY_PATH": lib_paths,
               "LD_LIBRARY_PATH": lib_paths,
               "PATH": bin_paths,
               "PYTHONPATH": python_paths}

        return ret
