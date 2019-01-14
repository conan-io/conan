import unittest

from conans.client.run_environment import RunEnvironment
from conans.test.utils.conanfile import ConanFileMock


class RunEnvironmentTest(unittest.TestCase):
    def run_vars_test(self):
        conanfile = ConanFileMock()
        conanfile.deps_cpp_info["one"].bin_paths.append("path/bin")
        conanfile.deps_cpp_info["two"].lib_paths.append("path/libs")
        be = RunEnvironment(conanfile)

        self.assertEqual(
            be.vars, {
                'PATH': ['path/bin'],
                'LD_LIBRARY_PATH': ['path/libs'],
                'DYLD_LIBRARY_PATH': ['path/libs']
            })
