from conan.api.subapi.new import NewAPI
from conan.internal.api.new.cmake_exe import cmake_exe_files
from conan.internal.api.new.cmake_lib import cmake_lib_files


conanws_yml = """\
packages:
  - path: liba
    ref: liba/0.1
  - path: libb
    ref: libb/0.1
  - path: app1
    ref: app1/0.1
"""

cmake = """\
cmake_minimum_required(VERSION 3.25)
project(monorepo CXX)

include(FetchContent)

function(add_project SUBFOLDER)
    message(STATUS "Adding project ${SUBFOLDER}")
    FetchContent_Declare(
        ${SUBFOLDER}
        SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/${SUBFOLDER}
        SYSTEM
        OVERRIDE_FIND_PACKAGE
    )
    FetchContent_MakeAvailable(${SUBFOLDER})
endfunction()

add_project(liba)
# They should be defined in the liba/CMakeLists.txt, but we can fix it here
add_library(liba::liba ALIAS liba)
add_project(libb)
add_library(libb::libb ALIAS libb)
add_project(app1)
"""

conanfile = '''\
from conan import Workspace
from conan import ConanFile
from conan.tools.cmake import CMakeDeps, CMakeToolchain, cmake_layout


class MyWs(ConanFile):
    """ This is a special conanfile, used only for workspace definition of layout
    and generators. It shouldn't have requirements, tool_requirements. It shouldn't have
    build() or package() methods
    """
    settings = "os", "compiler", "build_type", "arch"

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()
        tc = CMakeToolchain(self)
        tc.generate()

    def layout(self):
        cmake_layout(self)


class Ws(Workspace):
    def root_conanfile(self):
        return MyWs
'''

workspace_files = {"conanws.yml": conanws_yml,
                   "CMakeLists.txt": cmake,
                   "conanws.py": conanfile,
                   ".gitignore": "build"}
# liba
files = {f"liba/{k}": v for k, v in cmake_lib_files.items()}
workspace_files.update(files)
# libb
files = NewAPI.render(cmake_lib_files, {"requires": ["liba/0.1"], "name": "libb"})
files = {f"libb/{k}": v for k, v in files.items()}
workspace_files.update(files)
# app
files = NewAPI.render(cmake_exe_files, definitions={"name": "app1", "requires": ["libb/0.1"]})
files = {f"app1/{k}": v for k, v in files.items()}
workspace_files.update(files)
