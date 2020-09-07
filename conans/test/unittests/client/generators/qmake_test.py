import os
import unittest

from conans.client.generators.qmake import QmakeGenerator
from conans.model.build_info import CppInfo, DepCppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.settings import Settings
from conans.test.utils.mocks import TestBufferConanOutput


class QmakeGeneratorTest(unittest.TestCase):

    def system_libs_test(self):
        # https://github.com/conan-io/conan/issues/7558
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        cpp_info = CppInfo("MyPkg", "/rootpath")
        cpp_info.libs = ["mypkg"]
        cpp_info.system_libs = ["pthread"]
        conanfile.deps_cpp_info.add("MyPkg", DepCppInfo(cpp_info))
        generator = QmakeGenerator(conanfile)
        content = generator.content
        qmake_lines = content.splitlines()
        self.assertIn('CONAN_LIBS += -lmypkg', qmake_lines)
        self.assertIn('CONAN_SYSTEMLIBS += -lpthread', qmake_lines)

    def frameworks_test(self):
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        framework_path = os.getcwd()  # must exist, otherwise filtered by framework_paths
        cpp_info = CppInfo("MyPkg", "/rootpath")
        cpp_info.frameworks = ["HelloFramework"]
        cpp_info.frameworkdirs = [framework_path]
        conanfile.deps_cpp_info.add("MyPkg", DepCppInfo(cpp_info))
        generator = QmakeGenerator(conanfile)
        content = generator.content
        qmake_lines = content.splitlines()
        self.assertIn('CONAN_FRAMEWORKS += -framework HelloFramework', qmake_lines)
        self.assertIn('CONAN_FRAMEWORK_PATHS += -F%s' % framework_path, qmake_lines)
