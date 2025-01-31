from conan.api.subapi.new import NewAPI
from conan.internal.api.new.cmake_exe import cmake_exe_files
from conan.internal.api.new.cmake_lib import cmake_lib_files


conanws_yml = """\
editables:
  liba/0.1:
    path: liba
  libb/0.1:
    path: libb
  app1/0.1:
    path: app1
products:
- app1
"""

cmake = """\
cmake_minimum_required(VERSION 3.15)
project(monorepo CXX)

include(FetchContent)

function(add_project PROJECT_PATH_AND_NAME)
    message(STATUS "Adding project ${PROJECT_PATH_AND_NAME}")
    FetchContent_Declare(
        ${PROJECT_PATH_AND_NAME}
        SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}/${PROJECT_PATH_AND_NAME}
        SYSTEM
        OVERRIDE_FIND_PACKAGE
    )
    FetchContent_MakeAvailable(${PROJECT_PATH_AND_NAME})
endfunction()

add_project(liba)
# They should be defined in the liba/CMakeLists.txt, but we can fix it here
add_library(liba::liba ALIAS liba)
add_project(libb)
add_library(libb::libb ALIAS libb)
add_project(app1)
"""

workspace_files = {"conanws.yml": conanws_yml,
                   "CMakeLists.txt": cmake,
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
