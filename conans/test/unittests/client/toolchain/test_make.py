import platform
import textwrap
import unittest

from jinja2 import Template
from parameterized.parameterized import parameterized

from conans.client.build.compiler_flags import architecture_flag, build_type_flags
from conans.client.build.cppstd_flags import cppstd_flag_new
from conans.client.toolchain import MakeToolchain
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.test.utils.tools import TestBufferConanOutput
from conans.client.tools.oss import detected_architecture


class _MockSettings(object):
    build_type = None
    arch = None
    compiler = "gcc"
    compiler_version = "9"
    compiler_cppstd = None
    compiler_libcxx = None
    fields = []

    def __init__(self, build_type, arch, compiler_cppstd, compiler_libcxx):
        self.build_type = build_type
        self.arch = arch
        self.compiler_cppstd = compiler_cppstd
        self.compiler_libcxx = compiler_libcxx

    def constraint(self, _):
        return self

    def get_safe(self, name):
        name_internal = name.replace(".", "_")
        value = getattr(self, name_internal, None)
        return value

    def items(self):
        return {}


@unittest.skipUnless(platform.system() == "Linux", "Only for Linux")
class MakeToolchainTest(unittest.TestCase):
    @parameterized.expand([("Debug", "x86", "14", "libstdc++", False, False),
                           ("Release", "x86_64", "gnu14", "libstdc++11", True, False),
                           ("Release", "x86_64", "20", "libstdc++11", True, True)])
    def test_toolchain_linux(self, build_type, arch, cppstd, libcxx, shared, fpic):
        settings_mock = _MockSettings(build_type, arch, cppstd, libcxx)
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.options = {"shared": [True, False], "fPIC": [True, False]}
        conanfile.default_options = {"shared": shared, "fPIC": fpic}
        conanfile.initialize(settings_mock, EnvValues())
        toolchain = MakeToolchain(conanfile)
        content = toolchain.content

        expected_template = Template(textwrap.dedent("""
            # Conan generated toolchain file
            ifndef CONAN_TOOLCHAIN_INCLUDED
                CONAN_TOOLCHAIN_INCLUDED = TRUE
                CONAN_TC_BUILD_TYPE = {{build_type}}
                CONAN_TC_OS_HOST = None
                CONAN_TC_ARCH_HOST = {{arch_host}}
                CONAN_TC_TRIPLET_HOST = False
                CONAN_TC_OS_BUILD = Linux
                CONAN_TC_ARCH_BUILD = {{arch_build}}
                CONAN_TC_TRIPLET_BUILD = False
                CONAN_TC_OS_TARGET = None
                CONAN_TC_ARCH_TARGET = None
                CONAN_TC_TRIPLET_TARGET = None
                CONAN_TC_COMPILER = {{compiler}}
                CONAN_TC_COMPILER_VERSION = {{compiler_version}}
                CONAN_TC_COMPILER_RUNTIME = None
                CONAN_TC_LIBCXX = {{libcxx}}
                CONAN_TC_CPPSTD_FLAG = {{cppstd_flag}}
                CONAN_TC_ARCH_FLAG = {{arch_flag}}
                CONAN_TC_BUILD_TYPE_FLAGS = {{build_type_flags}}
                CONAN_TC_DEFINES ={{preserved_space}}

                CONAN_TC_SET_LIBCXX = True
                CONAN_TC_SET_CPPSTD = True
                CONAN_TC_SET_ARCH = True
                CONAN_TC_SET_FPIC = {{set_fpic}}
                CONAN_TC_SET_SHARED = {{set_shared}}

                CONAN_TC_CFLAGS += $(CONAN_TC_BUILD_TYPE_FLAGS)
                CONAN_TC_CXXFLAGS += $(CONAN_TC_BUILD_TYPE_FLAGS)

                ifeq ($(CONAN_TC_BUILD_TYPE),Release)
                    CONAN_TC_DEFINES += NDEBUG
                endif

                ifeq ($(CONAN_TC_SET_LIBCXX),True)
                    CONAN_TC_CLANG_BASED := $(if $(filter $(CONAN_TC_COMPILER),clang apple-clang),true)
                    ifeq ($(CONAN_TC_CLANG_BASED),True)
                        CONAN_TC_LIBSTDCXX_BASED := $(if $(filter $(CONAN_TC_LIBCXX),libstdc++ libstdc++11),true)
                        ifeq ($(CONAN_TC_LIBSTDCXX_BASED),True)
                            CONAN_TC_CXXFLAGS += -stdlib=libstdc++
                        else ifeq ($(CONAN_TC_LIBCXX),libc++)
                            CONAN_TC_CXXFLAGS += -stdlib=libc++
                        endif
                    else ifeq ($(CONAN_TC_COMPILER),sun-cc)
                        ifeq ($(CONAN_TC_LIBCXX),libCstd)
                            CONAN_TC_CXXFLAGS += -library=Cstd++
                        else ifeq ($(CONAN_TC_LIBCXX),libstdcxx)
                            CONAN_TC_CXXFLAGS += -library=stdcxx4
                        else ifeq ($(CONAN_TC_LIBCXX),libstlport)
                            CONAN_TC_CXXFLAGS += -library=stlport4
                        else ifeq ($(CONAN_TC_LIBCXX),libstdc++)
                            CONAN_TC_CXXFLAGS += -library=stdcpp
                        endif
                    endif
                    ifeq ($(CONAN_TC_LIBCXX),libstdc++11)
                        CONAN_TC_DEFINES += GLIBCXX_USE_CXX11_ABI=1
                    else ifeq ($(CONAN_TC_LIBCXX),libstdc++)
                        CONAN_TC_DEFINES += GLIBCXX_USE_CXX11_ABI=0
                    endif
                endif
                ifeq ($(CONAN_TC_SET_CPPSTD),True)
                    CONAN_TC_CXXFLAGS += $(CONAN_TC_CPPSTD_FLAG)
                endif
                ifeq ($(CONAN_TC_SET_ARCH),True)
                    CONAN_TC_CFLAGS += $(CONAN_TC_ARCH_FLAG)
                    CONAN_TC_CXXFLAGS += $(CONAN_TC_ARCH_FLAG)
                    CONAN_TC_SHARED_LINKER_FLAGS += $(CONAN_TC_ARCH_FLAG)
                    CONAN_TC_EXE_LINKER_FLAGS += $(CONAN_TC_ARCH_FLAG)
                endif
                ifeq ($(CONAN_TC_SET_FPIC),True)
                    CONAN_TC_CFLAGS += -fPIC
                    CONAN_TC_CXXFLAGS += -fPIC
                    CONAN_TC_SHARED_LINKER_FLAGS += -fPIC
                    CONAN_TC_EXE_LINKER_FLAGS += -pie
                endif
                ifeq ($(CONAN_TC_SET_SHARED),True)
                    CONAN_TC_LDFLAGS += -shared
                    CONAN_TC_LDFLAGS += $(CONAN_TC_SHARED_LINKER_FLAGS)
                else
                    CONAN_TC_LDFLAGS += $(CONAN_TC_EXE_LINKER_FLAGS)
                endif
            endif

            CONAN_TC_CPPFLAGS += $(addprefix -D,$(CONAN_TC_DEFINES))

            # Call this function in your Makefile to have Conan variables added to the standard variables
            # Example:  $(call CONAN_TC_SETUP)

            CONAN_TC_SETUP =  \\
                $(eval CFLAGS += $(CONAN_TC_CFLAGS)) ; \\
                $(eval CXXFLAGS += $(CONAN_TC_CXXFLAGS)) ; \\
                $(eval CPPFLAGS += $(CONAN_TC_CPPFLAGS)) ; \\
                $(eval LDFLAGS += $(CONAN_TC_LDFLAGS)) ;
        """))

        context = {
            "arch_host": conanfile.settings.get_safe("arch"),
            "arch_build": detected_architecture(),
            "compiler": conanfile.settings.get_safe("compiler"),
            "compiler_version": conanfile.settings.get_safe("compiler.version"),
            "arch_flag": architecture_flag(settings_mock),
            "cppstd_flag": cppstd_flag_new(conanfile.settings),
            "build_type_flags": " ".join(build_type_flags(conanfile.settings)),
            "build_type": build_type,
            "libcxx": libcxx,
            "set_shared": shared,
            "set_fpic": fpic,
            "preserved_space": " ",
        }
        #
        expected_content = expected_template.render(context)

        self.maxDiff = None
        self.assertIn(expected_content, content)
