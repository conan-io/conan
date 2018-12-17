import os
import re
import unittest
from collections import namedtuple

from nose.plugins.attrib import attr

from conans.client.conf import default_settings_yml
from conans.client.generators.cmake import CMakeGenerator
from conans.client.generators.cmake_multi import CMakeMultiGenerator
from conans.client.tools import replace_in_file
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


class CMakeGeneratorTest(unittest.TestCase):

    @attr('slow')
    def no_output_test(self):
        client = TestClient()
        client.run("new Test/1.0 --sources")
        cmakelists_path = os.path.join(client.current_folder, "src", "CMakeLists.txt")

        # Test output works as expected
        client.run("create . danimtb/testing")
        self.assertIn("Conan: Using cmake global configuration", client.out)
        self.assertIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertIn("Conan: Adjusting language standard", client.out)

        # Silence output
        replace_in_file(cmakelists_path,
                        "conan_basic_setup()",
                        "set(CONAN_CMAKE_SILENT_OUTPUT True)\nconan_basic_setup()",
                        output=client.user_io.out)
        client.run("create . danimtb/testing")
        self.assertNotIn("Conan: Using cmake global configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)

        # Use TARGETS
        replace_in_file(cmakelists_path, "conan_basic_setup()", "conan_basic_setup(TARGETS)",
                        output=client.user_io.out)
        client.run("create . danimtb/testing")
        self.assertNotIn("Conan: Using cmake targets configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)
