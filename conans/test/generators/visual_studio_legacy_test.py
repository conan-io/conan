import re
import unittest
import xml.etree.ElementTree

from conans.client.generators import VisualStudioLegacyGenerator

from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.client.generators.cmake import CMakeGenerator
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


class VisualStudioLegacyGeneratorTest(unittest.TestCase):
    def _createInfo(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
        cpp_info = CppInfo("dummy_root_folder1")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
        cpp_info = CppInfo("dummy_root_folder2")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = VisualStudioLegacyGenerator(conanfile)
        return generator.content

    def valid_xml_test(self):
        data = self._createInfo()
        try:
            xml.etree.ElementTree.fromstring(data)
        except xml.etree.ElementTree.ParseError as err:
            self.fail("Visual studio generated code is not valid! Error %s:\n%s " % (str(err), data))


    def variables_setup_test(self):
        content = self._createInfo()
        self.assertIn('AdditionalIncludeDirectories="&quot;dummy_root_folder1/include&quot;;&quot;dummy_root_folder2/include&quot;;"', content)
        self.assertIn('AdditionalLibraryDirectories="&quot;dummy_root_folder1/lib&quot;;&quot;dummy_root_folder2/lib&quot;;"', content)
