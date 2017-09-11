import unittest
import xml.etree.ElementTree

from conans.client.generators import VisualStudioLegacyGenerator

from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference


class VisualStudioLegacyGeneratorTest(unittest.TestCase):

    def valid_xml_test(self):
        conanfile = ConanFile(None, None, Settings({}), None)
        ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
        cpp_info = CppInfo("dummy_root_folder1")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
        cpp_info = CppInfo("dummy_root_folder2")
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = VisualStudioLegacyGenerator(conanfile)

        content = generator.content
        xml.etree.ElementTree.fromstring(content)

        self.assertIn('AdditionalIncludeDirectories="&quot;dummy_root_folder1'
                      '/include&quot;;&quot;dummy_root_folder2/include&quot;;"', content)
        self.assertIn('AdditionalLibraryDirectories="&quot;dummy_root_folder1'
                      '/lib&quot;;&quot;dummy_root_folder2/lib&quot;;"', content)
