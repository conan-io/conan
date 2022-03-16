from conans.cli.api.helpers.new.cmake_lib import source_cpp, source_h, test_main

conanfile_sources_v2 = """import os
from conan import ConanFile
from conan.tools.meson import MesonToolchain, Meson
from conan.tools.layout import basic_layout
from conan.tools.files import copy

class {{class_name or name}}Conan(ConanFile):
    name = "{{name}}"
    version = "{{version}}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "meson.build", "src/*"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        basic_layout(self)

    def generate(self):
        tc = MesonToolchain(self)
        tc.generate()

    def build(self):
        meson = Meson(self)
        meson.configure()
        meson.build()

    def package(self):
        meson = Meson(self)
        meson.install()
        # Meson cannot install dll/so in "bin" and .a/.lib in "lib"
        lib = os.path.join(self.package_folder, "lib")
        bin = os.path.join(self.package_folder, "bin")
        copy(self, "*.so", lib, bin)
        copy(self, "*.dll", lib, bin)

    def package_info(self):
        self.cpp_info.libs = ["{{name}}"]
"""


test_conanfile_v2 = """import os
from conan import ConanFile
from conan.tools.build import cross_building
from conan.tools.meson import MesonToolchain, Meson
from conan.tools.layout import basic_layout


class {{class_name or name}}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "PkgConfigDeps", "MesonToolchain"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def build(self):
        meson = Meson(self)
        meson.configure()
        meson.build()

    def layout(self):
        basic_layout(self)

    def test(self):
        if not cross_building(self):
            cmd = os.path.join(self.cpp.build.bindirs[0], "example")
            self.run(cmd, env="conanrun")
"""


_meson_build_test = """\
project('Test{{name}}', 'cpp')
{{name}} = dependency('{{name}}', version : '>=0.1')
executable('example', 'src/example.cpp', dependencies: {{name}})
"""


_meson_build = """\
project('{{name}} ', 'cpp')
library('{{name}}', 'src/{{name}}.cpp', install: true, install_dir: 'lib')
install_headers('src/{{name}}.h')
"""

meson_lib_files = {"conanfile.py": conanfile_sources_v2,
                   "src/{{name}}.cpp": source_cpp,
                   "src/{{name}}.h": source_h,
                   "meson.build": _meson_build,
                   "test_package/conanfile.py": test_conanfile_v2,
                   "test_package/src/example.cpp": test_main,
                   "test_package/meson.build": _meson_build_test}
