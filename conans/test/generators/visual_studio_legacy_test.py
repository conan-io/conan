import unittest
import xml.etree.ElementTree

from conans.client.generators import VisualStudioLegacyGenerator

from conans.model.settings import Settings
from conans.model.conan_file import ConanFile
from conans.model.build_info import CppInfo
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
import os
from conans.model.env_info import EnvValues


class VisualStudioLegacyGeneratorTest(unittest.TestCase):

    def valid_xml_test(self):
        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings({}), EnvValues())
        ref = ConanFileReference.loads("MyPkg/0.1@user/testing")
        folder1 = temp_folder()
        folder1 = folder1.replace("\\", "/")
        os.makedirs(os.path.join(folder1, "include"))
        os.makedirs(os.path.join(folder1, "lib"))
        cpp_info = CppInfo(folder1)
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        ref = ConanFileReference.loads("My.Fancy-Pkg_2/0.1@user/testing")
        folder2 = temp_folder()
        folder2 = folder2.replace("\\", "/")
        os.makedirs(os.path.join(folder2, "include"))
        os.makedirs(os.path.join(folder2, "lib"))
        cpp_info = CppInfo(folder2)
        conanfile.deps_cpp_info.update(cpp_info, ref.name)
        generator = VisualStudioLegacyGenerator(conanfile)

        content = generator.content
        xml.etree.ElementTree.fromstring(content)

        self.assertIn('AdditionalIncludeDirectories="&quot;%s/include&quot;;&quot;%s/include&quot;;"'
                      % (folder1, folder2), content)
        self.assertIn('AdditionalLibraryDirectories="&quot;%s/lib&quot;;&quot;%s/lib&quot;;"'
                      % (folder1, folder2), content)
