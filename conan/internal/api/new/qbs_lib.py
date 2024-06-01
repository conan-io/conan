from conan.internal.api.new.cmake_lib import source_cpp, source_h


conanfile_sources = '''
import os

from conan import ConanFile, tools
from conan.tools.qbs import Qbs
from conan.tools.files import copy, collect_libs

class {{package_name}}Recipe(ConanFile):
    name = "{{name}}"
    version = "{{version}}"

    exports_sources = "*.cpp", "*.h", "*.qbs"
    settings = "os", "compiler", "arch"

    def build(self):
        qbs = Qbs(self)
        qbs.profile = ""
        qbs.build()

    def package(self):
        qbs = Qbs(self)
        qbs.profile = ""
        qbs.install()

    def package_info(self):
        self.cpp_info.libs = collect_libs(self)
'''

qbs_file = '''
    Library {
        type: "staticlibrary"
        files: [ "{{name}}.h", "{{name}}.cpp" ]
        Depends { name: "cpp" }
        Depends { name: "bundle" }
        bundle.isBundle: false
        install: true
    }
'''

qbs_lib_files = {"conanfile.py": conanfile_sources,
                 "{{name}}.qbs": qbs_file,
                 "{{name}}.cpp": source_cpp,
                 "{{name}}.h": source_h}
