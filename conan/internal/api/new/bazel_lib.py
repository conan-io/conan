from conan.internal.api.new.cmake_lib import source_cpp, source_h, test_main

conanfile_sources_v2 = """
import os
from conan import ConanFile
from conan.tools.google import Bazel, bazel_layout
from conan.tools.files import copy

class {{package_name}}Recipe(ConanFile):
    name = "{{name}}"
    version = "{{version}}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "main/*", "WORKSPACE"
    generators = "BazelToolchain"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        bazel_layout(self)

    def build(self):
        bazel = Bazel(self)
        bazel.configure()
        bazel.build(label="//main:{{name}}")

    def package(self):
        dest_lib = os.path.join(self.package_folder, "lib")
        dest_bin = os.path.join(self.package_folder, "bin")
        build = os.path.join(self.build_folder, "bazel-bin", "main")
        copy(self, "*.so", build, dest_bin, keep_path=False)
        copy(self, "*.dll", build, dest_bin, keep_path=False)
        copy(self, "*.dylib", build, dest_bin, keep_path=False)
        copy(self, "*.a", build, dest_lib, keep_path=False)
        copy(self, "*.lib", build, dest_lib, keep_path=False)
        copy(self, "{{name}}.h", os.path.join(self.source_folder, "main"),
             os.path.join(self.package_folder, "include"), keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["{{name}}"]
"""


test_conanfile_v2 = """import os
from conan import ConanFile
from conan.tools.google import Bazel, bazel_layout
from conan.tools.build import can_run


class {{package_name}}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "BazelToolchain", "BazelDeps"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def build(self):
        bazel = Bazel(self)
        bazel.configure()
        bazel.build(label="//main:example")

    def layout(self):
        bazel_layout(self)

    def test(self):
        if can_run(self):
            cmd = os.path.join(self.cpp.build.bindir, "main", "example")
            self.run(cmd, env="conanrun")
"""


_bazel_build_test = """\
load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "example",
    srcs = ["example.cpp"],
    deps = [
        "@{{name}}//:{{name}}",
    ],
)
"""


_bazel_build = """\
load("@rules_cc//cc:defs.bzl", "cc_library")

cc_library(
    name = "{{name}}",
    srcs = ["{{name}}.cpp"],
    hdrs = ["{{name}}.h"],
)
"""

_bazel_workspace = " "  # Important not empty, so template doesn't discard it
_test_bazel_workspace = """
load("@//:dependencies.bzl", "load_conan_dependencies")
load_conan_dependencies()
"""


bazel_lib_files = {"conanfile.py": conanfile_sources_v2,
                   "main/{{name}}.cpp": source_cpp,
                   "main/{{name}}.h": source_h,
                   "main/BUILD": _bazel_build,
                   "WORKSPACE": _bazel_workspace,
                   "test_package/conanfile.py": test_conanfile_v2,
                   "test_package/main/example.cpp": test_main,
                   "test_package/main/BUILD": _bazel_build_test,
                   "test_package/WORKSPACE": _test_bazel_workspace}
