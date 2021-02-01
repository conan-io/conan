import textwrap
import unittest

from conan.tools.gnu import MakeToolchain
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.test.utils.tools import TestBufferConanOutput


class _MockSettings(object):
    fields = []

    def __init__(self):
        pass

    def constraint(self, _):
        return self

    def get_safe(self, name):
        name_internal = name.replace(".", "_")
        value = getattr(self, name_internal, None)
        return value

    def items(self):
        return {}


EXPECTED_OUT = textwrap.dedent("""
# Conan generated toolchain file
ifndef CONAN_TOOLCHAIN_INCLUDED
    CONAN_TOOLCHAIN_INCLUDED = TRUE

    # Recipe-Defined Variables
    TEST_VAR_01 = TEST_VAR_VAL_01
    TEST_VAR_02 = TEST_VAR_VAL_02

    # Automatic Conan pre-processor definition: build_type_define

    # Automatic Conan pre-processor definition: glibcxx_define

    # Recipe-Defined pre-processor definitions
    CONAN_TC_CPPFLAGS = -DTEST_PPD_01 -DTEST_PPD_02

endif
""")


class MakeToolchainTest(unittest.TestCase):

    def test_toolchain(self):
        settings_mock = _MockSettings()
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(settings_mock, EnvValues())
        toolchain = MakeToolchain(conanfile)
        toolchain.variables["TEST_VAR_01"] = "TEST_VAR_VAL_01"
        toolchain.variables["TEST_VAR_02"] = "TEST_VAR_VAL_02"
        toolchain.preprocessor_definitions["TEST_PPD_01"] = "TEST_PPD_VAL_01"
        toolchain.preprocessor_definitions["TEST_PPD_02"] = "TEST_PPD_VAL_02"
        content = toolchain.content
        print(content)
        self.maxDiff = None
        self.assertIn(EXPECTED_OUT, content)
