from conan.internal.api.new.cmake_lib import source_cpp, source_h, test_main


conanfile_exe = """
import os
from conan import ConanFile
from conan.tools.google import Bazel, bazel_layout
from conan.tools.files import copy


class {{package_name}}Recipe(ConanFile):
    name = "{{name}}"
    version = "{{version}}"
    package_type = "application"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "main/*", "WORKSPACE"

    generators = "BazelToolchain"

    def layout(self):
        bazel_layout(self)

    def build(self):
        bazel = Bazel(self)
        bazel.configure()
        bazel.build(label="//main:{{name}}")

    def package(self):
        dest_bin = os.path.join(self.package_folder, "bin")
        build = os.path.join(self.build_folder, "bazel-bin", "main")
        copy(self, "{{name}}", build, dest_bin, keep_path=False)
        copy(self, "{{name}}.exe", build, dest_bin, keep_path=False)
        """

test_conanfile_exe_v2 = """from conan import ConanFile
from conan.tools.build import can_run


class {{package_name}}Test(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        if can_run(self):
            self.run("{{name}}", env="conanrun")
"""

_bazel_build_exe = """\
load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "{{name}}",
    srcs = ["main.cpp", "{{name}}.cpp", "{{name}}.h"]
)
"""

_bazel_workspace = " "  # Important not empty, so template doesn't discard it


bazel_exe_files = {"conanfile.py": conanfile_exe,
                   "main/{{name}}.cpp": source_cpp,
                   "main/{{name}}.h": source_h,
                   "main/main.cpp": test_main,
                   "main/BUILD": _bazel_build_exe,
                   "WORKSPACE": _bazel_workspace,
                   "test_package/conanfile.py": test_conanfile_exe_v2
                   }
