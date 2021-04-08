import pytest
from mock import Mock

from conan.tools.cmake import CMakeDeps
from conans import ConanFile, Settings
from conans.client.tools import environment_append
from conans.errors import ConanException
from conans.model.build_info import CppInfo, DepCppInfo
from conans.model.env_info import EnvValues
from conans.util.conan_v2_mode import CONAN_V2_MODE_ENVVAR


def test_cpp_info_name_cmakedeps():
    conanfile = ConanFile(Mock(), None)
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]}), EnvValues())
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.names["cmake_find_package_multi"] = "MySuperPkg1"
    cpp_info.filenames["cmake_find_package_multi"] = "ComplexFileName1"
    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep.name = "OriginalDepName"
    conanfile_dep.version = "1.0"
    conanfile_dep.package_folder = "/path/to/folder_dep"
    ConanFile.dependencies = Mock()
    conanfile.dependencies.host_requires = [conanfile_dep]
    conanfile.dependencies.direct_host_requires = [conanfile_dep]

    cmakedeps = CMakeDeps(conanfile)
    files = cmakedeps.content
    assert "TARGET MySuperPkg1::MySuperPkg1" in files["ComplexFileName1Config.cmake"]
    assert 'set(MySuperPkg1_INCLUDE_DIRS_RELEASE "${MySuperPkg1_PACKAGE_FOLDER}/include")' in files["ComplexFileName1-release-x86-data.cmake"]

    with pytest.raises(ConanException,
                       match="'OriginalDepName' defines information for 'cmake_find_package_multi'"):
        with environment_append({CONAN_V2_MODE_ENVVAR: "1"}):
            _ = cmakedeps.content


def test_cpp_info_name_cmakedeps_components():
    conanfile = ConanFile(Mock(), None)
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release", "Debug"],
                                   "arch": ["x86", "x64"]}), EnvValues())
    conanfile.settings.build_type = "Debug"
    conanfile.settings.arch = "x64"

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.names["cmake_find_package_multi"] = "GlobakPkgName1"
    cpp_info.components["mycomp"].names["cmake_find_package_multi"] = "MySuperPkg1"
    cpp_info.filenames["cmake_find_package_multi"] = "ComplexFileName1"

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep.name = "OriginalDepName"
    conanfile_dep.version = "1.0"
    conanfile_dep.package_folder = "/path/to/folder_dep"
    ConanFile.dependencies = Mock()
    conanfile.dependencies.host_requires = [conanfile_dep]
    conanfile.dependencies.direct_host_requires = [conanfile_dep]

    cmakedeps = CMakeDeps(conanfile)
    files = cmakedeps.content
    assert "TARGET GlobakPkgName1::MySuperPkg1" in files["ComplexFileName1Config.cmake"]
    assert 'set(GlobakPkgName1_INCLUDE_DIRS_DEBUG "${GlobakPkgName1_PACKAGE_FOLDER}/include")' \
           in files["ComplexFileName1-debug-x64-data.cmake"]
    assert 'set(GlobakPkgName1_MySuperPkg1_INCLUDE_DIRS_DEBUG "${GlobakPkgName1_PACKAGE_FOLDER}/include")' \
           in files["ComplexFileName1-debug-x64-data.cmake"]

    with pytest.raises(ConanException,
                       match="'OriginalDepName' defines information for 'cmake_find_package_multi'"):
        with environment_append({CONAN_V2_MODE_ENVVAR: "1"}):
            _ = cmakedeps.content
