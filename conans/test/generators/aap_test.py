import re
import unittest
from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.aap import AapGenerator
from conans.model.build_info import DepsCppInfo
from conans.model.ref import ConanFileReference


class AapGeneratorTest(unittest.TestCase):
    def variables_setup_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = DepsCppInfo()
        cpp_info.defines = ["MYDEFINE1"]
        conanfile.deps_cpp_info.update(cpp_info, ref)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = DepsCppInfo()
        cpp_info.defines = ["MYDEFINE2"]
        conanfile.deps_cpp_info.update(cpp_info, ref)
        generator = AapGenerator(conanfile)
        content = generator.content
        content_lines = content.splitlines()
        self.assertIn('DEFINE += -DMYDEFINE2 -DMYDEFINE1', content_lines)
