from conan.internal.api.new.autotools_lib import configure_ac, makefile_am

conanfile_exe = """
import os

from conan import ConanFile
from conan.tools.gnu import AutotoolsToolchain, Autotools
from conan.tools.layout import basic_layout
from conan.tools.files import chdir


class {{package_name}}Conan(ConanFile):
    name = "{{name}}"
    version = "{{version}}"
    package_type = "application"

    # Optional metadata
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "configure.ac", "Makefile.am", "src/*"

    def layout(self):
        basic_layout(self)

    def generate(self):
        at_toolchain = AutotoolsToolchain(self)
        at_toolchain.generate()

    def build(self):
        autotools = Autotools(self)
        autotools.autoreconf()
        autotools.configure()
        autotools.make()

    def package(self):
        autotools = Autotools(self)
        autotools.install()
"""
makefile_am_exe = """
bin_PROGRAMS = {{name}}
{{name}}_SOURCES = main.cpp
"""

test_conanfile_exe_v2 = """
import os
from conan import ConanFile
from conan.tools.build import can_run
from conan.tools.layout import basic_layout


class {{package_name}}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def layout(self):
        basic_layout(self)

    def test(self):
        if can_run(self):
            self.run("{{name}}", env="conanrun")
"""

test_exe = r"""#include <iostream>

int main() {
    #ifdef NDEBUG
    std::cout << "{{name}}/{{version}}: Hello World Release!\n";
    #else
    std::cout << "{{name}}/{{version}}: Hello World Debug!\n";
    #endif
}
"""


autotools_exe_files = {"conanfile.py": conanfile_exe,
                       "src/main.cpp": test_exe,
                       "configure.ac": configure_ac,
                       "Makefile.am": makefile_am,
                       "src/Makefile.am": makefile_am_exe,
                       "test_package/conanfile.py": test_conanfile_exe_v2
                       }
