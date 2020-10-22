# coding=utf-8

import unittest

from conans.client.run_environment import RunEnvironment
from conans.test.utils.mocks import ConanFileMock


class RunEnvironmentTest(unittest.TestCase):

    def test_run_vars(self):
        conanfile = ConanFileMock()
        conanfile.deps_cpp_info["one"].bin_paths.append("path/bin")
        conanfile.deps_cpp_info["two"].lib_paths.append("path/libs")
        be = RunEnvironment(conanfile)

        self.assertEqual(be.vars,  {'PATH': ['path/bin'],
                                    'LD_LIBRARY_PATH': ['path/libs'],
                                    'DYLD_LIBRARY_PATH': ['path/libs']})

    def test_apple_frameworks(self):
        conanfile = ConanFileMock()
        conanfile.deps_cpp_info["one"].bin_paths.append("path/bin")
        conanfile.deps_cpp_info["two"].lib_paths.append("path/libs")
        conanfile.deps_cpp_info["one"].framework_paths.append("path/Frameworks")
        be = RunEnvironment(conanfile)

        self.assertEqual(be.vars, {'PATH': ['path/bin'],
                                   'LD_LIBRARY_PATH': ['path/libs'],
                                   'DYLD_LIBRARY_PATH': ['path/libs'],
                                   'DYLD_FRAMEWORK_PATH': ['path/Frameworks']})
