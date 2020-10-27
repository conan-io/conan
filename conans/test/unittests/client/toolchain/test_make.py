import platform
import textwrap
import unittest

from parameterized.parameterized import parameterized

from conans.client.toolchain import MakeToolchain
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.test.utils.tools import TestBufferConanOutput


class _MockSettings(object):
    build_type = None
    arch = None
    compiler = None
    compiler_version = "9"
    compiler_cppstd = None
    compiler_libcxx = None
    fields = []

    def __init__(self, build_type, arch, comp, comp_ver, comp_cppstd, comp_libcxx):
        self.build_type = build_type
        self.arch = arch
        self.compiler = comp
        self.compiler_version = comp_ver
        self.compiler_cppstd = comp_cppstd
        self.compiler_libcxx = comp_libcxx

    def constraint(self, _):
        return self

    def get_safe(self, name):
        name_internal = name.replace(".", "_")
        value = getattr(self, name_internal, None)
        return value

    def items(self):
        return {}


EXPECTED_OUT_1 = textwrap.dedent("""
# Conan generated toolchain file
ifndef CONAN_TOOLCHAIN_INCLUDED
    CONAN_TOOLCHAIN_INCLUDED = TRUE

    # Automatic Conan Toolchain Variables
    CONAN_TC_BUILD_TYPE = Debug
    CONAN_TC_ARCH_HOST = x86
    CONAN_TC_OS_BUILD = Linux
    CONAN_TC_ARCH_BUILD = x86_64
    CONAN_TC_COMPILER = gcc
    CONAN_TC_COMPILER_VERSION = 9

    # Recipe-Defined Variables
    TEST_VAR_01 = TEST_VAR_VAL_01
    TEST_VAR_02 = TEST_VAR_VAL_02

    # Automatic Conan pre-processor definition: build_type_define

    # Automatic Conan pre-processor definition: glibcxx_define
    CONAN_TC_CPPFLAGS += -D_GLIBCXX_USE_CXX11_ABI=0

    # Recipe-Defined pre-processor definitions
    CONAN_TC_CPPFLAGS = -DTEST_PPD_01 -DTEST_PPD_02

    # C++ Standard Library compiler flag

    # C++ Standard compiler flag
    CONAN_TC_CXXFLAGS += -std=c++14

    # Build Type compiler flag
    CONAN_TC_CFLAGS += -g
    CONAN_TC_CXXFLAGS += -g

    # Architecture compiler flag
    CONAN_TC_CFLAGS += -m32
    CONAN_TC_CXXFLAGS += -m32

    # Position-independent code

endif

# Call this function in your Makefile to have Conan variables added to the standard variables
# Example:  $(call CONAN_TC_SETUP)

CONAN_TC_SETUP = $(eval CFLAGS += $(CONAN_TC_CFLAGS)) ; \\
                 $(eval CXXFLAGS += $(CONAN_TC_CXXFLAGS)) ; \\
                 $(eval CPPFLAGS += $(CONAN_TC_CPPFLAGS)) ; \\
                 $(eval LDFLAGS += $(CONAN_TC_LDFLAGS)) ;
""")

EXPECTED_OUT_2 = textwrap.dedent("""
# Conan generated toolchain file
ifndef CONAN_TOOLCHAIN_INCLUDED
    CONAN_TOOLCHAIN_INCLUDED = TRUE

    # Automatic Conan Toolchain Variables
    CONAN_TC_BUILD_TYPE = Release
    CONAN_TC_ARCH_HOST = x86_64
    CONAN_TC_OS_BUILD = Linux
    CONAN_TC_ARCH_BUILD = x86_64
    CONAN_TC_COMPILER = gcc
    CONAN_TC_COMPILER_VERSION = 9

    # Recipe-Defined Variables
    TEST_VAR_01 = TEST_VAR_VAL_01
    TEST_VAR_02 = TEST_VAR_VAL_02

    # Automatic Conan pre-processor definition: build_type_define
    CONAN_TC_CPPFLAGS += -DNDEBUG

    # Automatic Conan pre-processor definition: glibcxx_define
    CONAN_TC_CPPFLAGS += -D_GLIBCXX_USE_CXX11_ABI=0

    # Recipe-Defined pre-processor definitions
    CONAN_TC_CPPFLAGS = -DTEST_PPD_01 -DTEST_PPD_02

    # C++ Standard Library compiler flag

    # C++ Standard compiler flag
    CONAN_TC_CXXFLAGS += -std=gnu++14

    # Build Type compiler flag
    CONAN_TC_CFLAGS += -O3 -s
    CONAN_TC_CXXFLAGS += -O3 -s

    # Architecture compiler flag
    CONAN_TC_CFLAGS += -m64
    CONAN_TC_CXXFLAGS += -m64

    # Position-independent code

endif

# Call this function in your Makefile to have Conan variables added to the standard variables
# Example:  $(call CONAN_TC_SETUP)

CONAN_TC_SETUP = $(eval CFLAGS += $(CONAN_TC_CFLAGS)) ; \\
                 $(eval CXXFLAGS += $(CONAN_TC_CXXFLAGS)) ; \\
                 $(eval CPPFLAGS += $(CONAN_TC_CPPFLAGS)) ; \\
                 $(eval LDFLAGS += $(CONAN_TC_LDFLAGS)) ;
""")

EXPECTED_OUT_3 = textwrap.dedent("""
# Conan generated toolchain file
ifndef CONAN_TOOLCHAIN_INCLUDED
    CONAN_TOOLCHAIN_INCLUDED = TRUE

    # Automatic Conan Toolchain Variables
    CONAN_TC_BUILD_TYPE = Release
    CONAN_TC_ARCH_HOST = x86_64
    CONAN_TC_OS_BUILD = Linux
    CONAN_TC_ARCH_BUILD = x86_64
    CONAN_TC_COMPILER = clang
    CONAN_TC_COMPILER_VERSION = 8.0

    # Recipe-Defined Variables
    TEST_VAR_01 = TEST_VAR_VAL_01
    TEST_VAR_02 = TEST_VAR_VAL_02

    # Automatic Conan pre-processor definition: build_type_define
    CONAN_TC_CPPFLAGS += -DNDEBUG

    # Automatic Conan pre-processor definition: glibcxx_define

    # Recipe-Defined pre-processor definitions
    CONAN_TC_CPPFLAGS = -DTEST_PPD_01 -DTEST_PPD_02

    # C++ Standard Library compiler flag
    CONAN_TC_CXXFLAGS += -stdlib=libc++

    # C++ Standard compiler flag
    CONAN_TC_CXXFLAGS += -std=c++2a

    # Build Type compiler flag
    CONAN_TC_CFLAGS += -O3
    CONAN_TC_CXXFLAGS += -O3

    # Architecture compiler flag
    CONAN_TC_CFLAGS += -m64
    CONAN_TC_CXXFLAGS += -m64

    # Position-independent code
    CONAN_TC_CFLAGS += -fPIC
    CONAN_TC_CXXFLAGS += -fPIC
    CONAN_TC_SHARED_LINKER_FLAGS += -fPIC

endif

# Call this function in your Makefile to have Conan variables added to the standard variables
# Example:  $(call CONAN_TC_SETUP)

CONAN_TC_SETUP = $(eval CFLAGS += $(CONAN_TC_CFLAGS)) ; \\
                 $(eval CXXFLAGS += $(CONAN_TC_CXXFLAGS)) ; \\
                 $(eval CPPFLAGS += $(CONAN_TC_CPPFLAGS)) ; \\
                 $(eval LDFLAGS += $(CONAN_TC_LDFLAGS)) ;
""")

EXPECTED_OUT_4 = textwrap.dedent("""
# Conan generated toolchain file
ifndef CONAN_TOOLCHAIN_INCLUDED
    CONAN_TOOLCHAIN_INCLUDED = TRUE

    # Automatic Conan Toolchain Variables
    CONAN_TC_BUILD_TYPE = Release
    CONAN_TC_ARCH_HOST = x86_64
    CONAN_TC_OS_BUILD = Linux
    CONAN_TC_ARCH_BUILD = x86_64
    CONAN_TC_COMPILER = clang
    CONAN_TC_COMPILER_VERSION = 8.0

    # Recipe-Defined Variables
    TEST_VAR_01 = TEST_VAR_VAL_01
    TEST_VAR_02 = TEST_VAR_VAL_02

    # Automatic Conan pre-processor definition: build_type_define
    CONAN_TC_CPPFLAGS += -DNDEBUG

    # Automatic Conan pre-processor definition: glibcxx_define
    CONAN_TC_CPPFLAGS += -D_GLIBCXX_USE_CXX11_ABI=1

    # Recipe-Defined pre-processor definitions
    CONAN_TC_CPPFLAGS = -DTEST_PPD_01 -DTEST_PPD_02

    # C++ Standard Library compiler flag
    CONAN_TC_CXXFLAGS += -stdlib=libstdc++

    # C++ Standard compiler flag
    CONAN_TC_CXXFLAGS += -std=c++2a

    # Build Type compiler flag
    CONAN_TC_CFLAGS += -O3
    CONAN_TC_CXXFLAGS += -O3

    # Architecture compiler flag
    CONAN_TC_CFLAGS += -m64
    CONAN_TC_CXXFLAGS += -m64

    # Position-independent code
    CONAN_TC_CFLAGS += -fPIC
    CONAN_TC_CXXFLAGS += -fPIC
    CONAN_TC_SHARED_LINKER_FLAGS += -fPIC

endif

# Call this function in your Makefile to have Conan variables added to the standard variables
# Example:  $(call CONAN_TC_SETUP)

CONAN_TC_SETUP = $(eval CFLAGS += $(CONAN_TC_CFLAGS)) ; \\
                 $(eval CXXFLAGS += $(CONAN_TC_CXXFLAGS)) ; \\
                 $(eval CPPFLAGS += $(CONAN_TC_CPPFLAGS)) ; \\
                 $(eval LDFLAGS += $(CONAN_TC_LDFLAGS)) ;
""")


class MakeToolchainTest(unittest.TestCase):
    @parameterized.expand([
        ("Debug", "x86", "gcc", "9", "14", "libstdc++", False, False, EXPECTED_OUT_1),
        ("Release", "x86_64", "gcc", "9", "gnu14", "libstdc++", True, False, EXPECTED_OUT_2),
        ("Release", "x86_64", "clang", "8.0", "20", "libc++", True, True, EXPECTED_OUT_3),
        ("Release", "x86_64", "clang", "8.0", "20", "libstdc++11", True, True, EXPECTED_OUT_4),
    ])
    @unittest.skipUnless(platform.system() in ["Linux", "Macos"], "Requires make")
    def test_toolchain_posix(self, build_type, arch, compiler, compiler_ver, compiler_cppstd,
                             compiler_libcxx, shared, fpic, expected):

        settings_mock = _MockSettings(build_type, arch, compiler, compiler_ver, compiler_cppstd,
                                      compiler_libcxx)
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.options = {"shared": [True, False], "fPIC": [True, False]}
        conanfile.default_options = {"shared": shared, "fPIC": fpic}
        conanfile.initialize(settings_mock, EnvValues())
        toolchain = MakeToolchain(conanfile)
        toolchain.variables["TEST_VAR_01"] = "TEST_VAR_VAL_01"
        toolchain.variables["TEST_VAR_02"] = "TEST_VAR_VAL_02"
        toolchain.preprocessor_definitions["TEST_PPD_01"] = "TEST_PPD_VAL_01"
        toolchain.preprocessor_definitions["TEST_PPD_02"] = "TEST_PPD_VAL_02"
        content = toolchain.content
        self.maxDiff = None
        self.assertIn(expected, content)
