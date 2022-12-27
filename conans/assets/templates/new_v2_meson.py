from conans.assets.templates.new_v2_cmake import source_cpp, source_h, test_main

conanfile_sources_v2 = """import os
from conan import ConanFile
from conan.tools.meson import MesonToolchain, Meson
from conan.tools.layout import basic_layout
from conan.tools.files import copy

class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False], "fPIC": [True, False]}}
    default_options = {{"shared": False, "fPIC": True}}

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

    def package_info(self):
        self.cpp_info.libs = ["{name}"]
"""


test_conanfile_v2 = """import os
from conan import ConanFile
from conans import tools
from conan.tools.meson import MesonToolchain, Meson
from conan.tools.layout import basic_layout


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualBuildEnv and VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "PkgConfigDeps", "MesonToolchain", "VirtualBuildEnv", "VirtualRunEnv"
    apply_env = False

    def build(self):
        meson = Meson(self)
        meson.configure()
        meson.build()

    def layout(self):
        basic_layout(self)

    def test(self):
        if not tools.cross_building(self):
            cmd = os.path.join(self.cpp.build.bindirs[0], "example")
            self.run(cmd, env="conanrun")
"""


_meson_build_test = """\
project('Test{name}', 'cpp')
{name} = dependency('{name}', version : '>=0.1')
executable('example', 'src/example.cpp', dependencies: {name})
"""


_meson_build = """\
project('{name} ', 'cpp')
library('{name}', 'src/{name}.cpp', install: true)
install_headers('src/{name}.h')
"""


def get_meson_lib_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_sources_v2.format(name=name, version=version,
                                                         package_name=package_name),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "src/{}.h".format(name): source_h.format(name=name, version=version),
             "meson.build": _meson_build.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_v2.format(name=name,
                                                                   version=version,
                                                                   package_name=package_name),
             "test_package/src/example.cpp": test_main.format(name=name),
             "test_package/meson.build": _meson_build_test.format(name=name)}
    return files


conanfile_exe = """from conan import ConanFile
from conan.tools.meson import MesonToolchain, Meson


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "meson.build", "src/*"

    def layout(self):
        self.folders.build = "build"

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
"""

test_conanfile_exe_v2 = """import os
from conan import ConanFile
from conans import tools


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "VirtualRunEnv"
    apply_env = False

    def test(self):
        if not tools.cross_building(self):
            self.run("{name}", env="conanrun")
"""

_meson_build_exe = """\
project('{name} ', 'cpp')
executable('{name}', 'src/{name}.cpp', 'src/main.cpp', install: true)
"""


def get_meson_exe_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_exe.format(name=name, version=version,
                                                  package_name=package_name),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "src/{}.h".format(name): source_h.format(name=name, version=version),
             "src/main.cpp": test_main.format(name=name),
             "meson.build": _meson_build_exe.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_exe_v2.format(name=name,
                                                                       version=version,
                                                                       package_name=package_name)
             }
    return files
