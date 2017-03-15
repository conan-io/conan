import unittest

from conans.client.run_environment import RunEnvironment


class CppInfo(object):

    def __init__(self):
        self.bin_paths = []
        self.lib_paths = []


class MockDepsCppInfo(dict):

    def __init__(self):
        self["one"] = CppInfo()
        self["two"] = CppInfo()

    @property
    def deps(self):
        return self.keys()


class MockConanfile(object):

    def __init__(self):
        self.deps_cpp_info = MockDepsCppInfo()


class RunEnvironmentTest(unittest.TestCase):

    def run_vars_test(self):
        conanfile = MockConanfile()
        conanfile.deps_cpp_info["one"].bin_paths.append("path/bin")
        conanfile.deps_cpp_info["two"].lib_paths.append("path/libs")
        be = RunEnvironment(conanfile)

        self.assertEquals(be.vars,  {'PATH': ['path/bin'],
                                     'LD_LIBRARY_PATH': ['path/libs'],
                                     'DYLIB_LIBRARY_PATH': ['path/libs']})
