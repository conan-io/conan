"""
CROOSTOOL https://github.com/bazelbuild/bazel/blob/cb0fb033bad2a73e0457f206afb87e195be93df2/tools/cpp/CROSSTOOL
CROSS-COMPILING WITH BAZEL https://ltekieli.com/cross-compiling-with-bazel/
BAZELRC https://bazel.build/run/bazelrc
CLI OPTIONS https://bazel.build/reference/command-line-reference

The goal of this toolchain is to be able to load some common configuration for Bazel projects:

    $ bazel --bazelrc="bazel-conan-generators/conan_bzl.rc" build --config=conan-config //main:my-lib
"""


from conan.tools.apple.apple import apple_min_version_flag, is_apple_os, to_apple_arch, apple_sdk_path
from conan.tools.apple.apple import apple_min_version_flag, is_apple_os, to_apple_arch, \
    apple_sdk_path
from conan.tools.apple.apple import get_apple_sdk_fullname
from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import architecture_flag, build_type_flags, cppstd_flag, \
    build_type_link_flags, \
    libcxx_flags
from conan.tools.gnu.get_gnu_triplet import _get_gnu_triplet
from conan.tools.microsoft import msvc_runtime_flag


class AutotoolsToolchain:

    filename = "conan_bzl.rc"

    def __init__(self, conanfile, namespace=None, prefix="/"):
        self._conanfile = conanfile
        self._namespace = namespace

        # Flags
        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_ldflags = []
        self.extra_defines = []

        # Defines
        self.copts = []
        self.fpic = ""  # --[no]force_pic
        self.conlyopt = []
        self.cxxopt = []
        self.linkopts = []
        self.strip = ""
        self.cpu = ""
        self.compilation_mode = "fastbuild"  #  'fastbuild', 'dbg', 'opt'
        self.crosstool_top = ""
        self.config = ""
        self.compiler = ""

    def _get_msvc_runtime_flag(self):
        flag = msvc_runtime_flag(self._conanfile)
        if flag:
            flag = "-{}".format(flag)
        return flag

    @staticmethod
    def _filter_list_empty_fields(v):
        return list(filter(bool, v))

    @property
    def cxxflags(self):
        fpic = "-fPIC" if self.fpic else None
        ret = [self.libcxx, self.cppstd, self.arch_flag, fpic, self.msvc_runtime_flag,
               self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        ret = ret + self.build_type_flags + apple_flags + conf_flags + self.extra_cxxflags
        return self._filter_list_empty_fields(ret)

    @property
    def cflags(self):
        fpic = "-fPIC" if self.fpic else None
        ret = [self.arch_flag, fpic, self.msvc_runtime_flag, self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        ret = ret + self.build_type_flags + apple_flags + conf_flags + self.extra_cflags
        return self._filter_list_empty_fields(ret)

    @property
    def ldflags(self):
        ret = [self.arch_flag, self.sysroot_flag]
        apple_flags = [self.apple_isysroot_flag, self.apple_arch_flag, self.apple_min_version_flag]
        conf_flags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[],
                                              check_type=list)
        conf_flags.extend(self._conanfile.conf.get("tools.build:exelinkflags", default=[],
                                                   check_type=list))
        linker_scripts = self._conanfile.conf.get("tools.build:linker_scripts", default=[], check_type=list)
        conf_flags.extend(["-T'" + linker_script + "'" for linker_script in linker_scripts])
        ret = ret + apple_flags + conf_flags + self.build_type_link_flags + self.extra_ldflags
        return self._filter_list_empty_fields(ret)

    @property
    def defines(self):
        conf_flags = self._conanfile.conf.get("tools.build:defines", default=[], check_type=list)
        ret = [self.ndebug, self.gcc_cxx11_abi] + conf_flags + self.extra_defines
        return self._filter_list_empty_fields(ret)
