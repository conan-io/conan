import platform

from conans.assets.templates.new_v2_cmake import source_cpp, source_h, test_main

conanfile_sources_v2 = """
import os
from conan import ConanFile
from conan.errors import ConanException
from conan.tools.google import Bazel, bazel_layout
from conan.tools.files import copy

class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False], "fPIC": [True, False]}}
    default_options = {{"shared": False, "fPIC": True}}

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "main/*", "WORKSPACE"
    generators = "BazelToolchain"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        # DEPRECATED: Default generators folder will be "conan" in Conan 2.x
        self.folders.generators = "conan"
        bazel_layout(self)

    def build(self):
        bazel = Bazel(self)
        # On Linux platforms, Bazel creates both shared and static libraries by default, and
        # it is getting naming conflicts if we use the cc_shared_library rule
        if self.options.shared and self.settings.os != "Linux":
            # We need to add '--experimental_cc_shared_library' because the project uses
            # cc_shared_library to create shared libraries
            bazel.build(args=["--experimental_cc_shared_library"], target="//main:{name}_shared")
        else:
            bazel.build(target="//main:{name}")

    def package(self):
        dest_lib = os.path.join(self.package_folder, "lib")
        dest_bin = os.path.join(self.package_folder, "bin")
        build = os.path.join(self.build_folder, "bazel-bin", "main")
        copy(self, "*.so", build, dest_lib, keep_path=False)
        copy(self, "*.dll", build, dest_bin, keep_path=False)
        copy(self, "*.dylib", build, dest_lib, keep_path=False)
        copy(self, "*.a", build, dest_lib, keep_path=False)
        copy(self, "*.lib", build, dest_lib, keep_path=False)
        copy(self, "{name}.h", os.path.join(self.source_folder, "main"),
             os.path.join(self.package_folder, "include"), keep_path=False)

    def package_info(self):
        if self.options.shared and self.settings.os != "Linux":
            self.cpp_info.libs = ["{name}_shared"]
        else:
            self.cpp_info.libs = ["{name}"]
"""


test_conanfile_v2 = """import os
from conan import ConanFile
from conan.tools.google import Bazel, bazel_layout
from conan.tools.build import cross_building


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualBuildEnv and VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "BazelToolchain", "BazelDeps", "VirtualBuildEnv", "VirtualRunEnv"
    apply_env = False

    def requirements(self):
        self.requires(self.tested_reference_str)

    def build(self):
        bazel = Bazel(self)
        bazel.build(target="//main:example")

    def layout(self):
        # DEPRECATED: Default generators folder will be "conan" in Conan 2.x
        self.folders.generators = "conan"
        bazel_layout(self)

    def test(self):
        if not cross_building(self):
            cmd = os.path.join(self.cpp.build.bindirs[0], "main", "example")
            self.run(cmd, env="conanrun")
"""


_bazel_build_test = """\
load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "example",
    srcs = ["example.cpp"],
    deps = [
        "@{name}//:{name}",
    ],
)
"""


_bazel_build_linux = """\
load("@rules_cc//cc:defs.bzl", "cc_library")

cc_library(
    name = "{name}",
    srcs = ["{name}.cpp"],
    hdrs = ["{name}.h"],
)
"""

_bazel_build = """\
load("@rules_cc//cc:defs.bzl", "cc_library")

cc_library(
    name = "{name}",
    srcs = ["{name}.cpp"],
    hdrs = ["{name}.h"],
)

cc_shared_library(
    name = "{name}_shared",
    shared_lib_name = "lib{name}_shared.{ext}",
    deps = [":{name}"],
)
"""

_bazel_workspace = ""
_test_bazel_workspace = """
load("@//conan:dependencies.bzl", "load_conan_dependencies")
load_conan_dependencies()
"""


conanfile_exe = """
import os
from conan import ConanFile
from conan.tools.google import Bazel, bazel_layout
from conan.tools.files import copy


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "main/*", "WORKSPACE"

    generators = "BazelToolchain"

    def layout(self):
        # DEPRECATED: Default generators folder will be "conan" in Conan 2.x
        self.folders.generators = "conan"
        bazel_layout(self)

    def build(self):
        bazel = Bazel(self)
        bazel.build()

    def package(self):
        dest_bin = os.path.join(self.package_folder, "bin")
        build = os.path.join(self.build_folder, "bazel-bin", "main")
        copy(self, "{name}", build, dest_bin, keep_path=False)
        copy(self, "{name}.exe", build, dest_bin, keep_path=False)
        """

test_conanfile_exe_v2 = """import os
from conan import ConanFile
from conan.tools.build import cross_building


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "VirtualRunEnv"
    apply_env = False

    def test(self):
        if not cross_building(self):
            self.run("{name}", env="conanrun")
"""

_bazel_build_exe = """\
load("@rules_cc//cc:defs.bzl", "cc_binary")

cc_binary(
    name = "{name}",
    srcs = ["main.cpp", "{name}.cpp", "{name}.h"]
)
"""


def _get_bazel_build(name):
    _bazel_build_template = ""
    if platform.system() == "Windows":
        _bazel_build_template = _bazel_build.format(name=name, ext="dll")
    elif platform.system() == "Darwin":
        _bazel_build_template = _bazel_build.format(name=name, ext="dylib")
    else:  # Assuming Linux
        _bazel_build_template = _bazel_build_linux.format(name=name)
    return _bazel_build_template


def get_bazel_lib_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_sources_v2.format(name=name, version=version,
                                                         package_name=package_name),
             "main/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "main/{}.h".format(name): source_h.format(name=name, version=version),
             "main/BUILD": _get_bazel_build(name),
             "WORKSPACE": _bazel_workspace.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_v2.format(name=name, version=version,
                                                                   package_name=package_name),
             "test_package/main/example.cpp": test_main.format(name=name),
             "test_package/main/BUILD": _bazel_build_test.format(name=name),
             "test_package/WORKSPACE": _test_bazel_workspace.format(name=name, version=version)}
    return files


def get_bazel_exe_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_exe.format(name=name, version=version,
                                                  package_name=package_name),
             "main/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "main/{}.h".format(name): source_h.format(name=name, version=version),
             "main/main.cpp": test_main.format(name=name),
             "main/BUILD": _bazel_build_exe.format(name=name, version=version),
             "WORKSPACE": _bazel_workspace.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_exe_v2.format(name=name, version=version,
                                                                       package_name=package_name)
             }
    return files
