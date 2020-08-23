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
        # https://github.com/conan-io/conan/issues/7564
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues())
        cpp_info = CppInfo("MyPkg", "/rootpath")
        cpp_info.filter_empty = False
        cpp_info.frameworks = ["myframework"]
        cpp_info.frameworkdirs = ["my/framework/dir"]
        conanfile.deps_cpp_info.add("MyPkg", DepCppInfo(cpp_info))
        generator = QmakeGenerator(conanfile)
        content = generator.content
        self.assertIn("CONAN_FRAMEWORKS += -framework myframework", content)
        self.assertIn("CONAN_FRAMEWORKSDIRS += -F/rootpath/my/framework/dir", content)
        self.assertIn("CONAN_FRAMEWORKS_MYPKG += -framework myframework", content)
        self.assertIn("CONAN_FRAMEWORKSDIRS_MYPKG += -F/rootpath/my/framework/dir", content)
        self.assertIn("LIBS += $$CONAN_FRAMEWORKSDIRS_RELEASE", content)
        self.assertIn("LIBS += $$CONAN_FRAMEWORKS_RELEASE", content)
