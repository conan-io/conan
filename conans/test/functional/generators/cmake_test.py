import os
import unittest

from nose.plugins.attrib import attr

from conans.client.tools import replace_in_file
from conans.test.utils.tools import TestClient


class CMakeGeneratorTest(unittest.TestCase):

    @attr('slow')
    def no_output_test(self):
        client = TestClient()
        client.run("new Test/1.0 --sources")
        cmakelists_path = os.path.join(client.current_folder, "src", "CMakeLists.txt")

        # Test output works as expected
        client.run("install .")
        # No need to do a full create, the build --configure is good
        client.run("build . --configure")
        self.assertIn("Conan: Using cmake global configuration", client.out)
        self.assertIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertIn("Conan: Adjusting language standard", client.out)

        # Silence output
        replace_in_file(cmakelists_path,
                        "conan_basic_setup()",
                        "set(CONAN_CMAKE_SILENT_OUTPUT True)\nconan_basic_setup()",
                        output=client.user_io.out)
        client.run("build . --configure")
        self.assertNotIn("Conan: Using cmake global configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)

        # Use TARGETS
        replace_in_file(cmakelists_path, "conan_basic_setup()", "conan_basic_setup(TARGETS)",
                        output=client.user_io.out)
        client.run("build . --configure")
        self.assertNotIn("Conan: Using cmake targets configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)
