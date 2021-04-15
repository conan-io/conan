from mock import Mock

from conan.tools.cmake import CMakeDeps
from conans import ConanFile, Settings
from conans.model.build_info import CppInfo
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.env_info import EnvValues


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
    cpp_info.set_property("cmake_target_name", "MySuperPkg1")
    cpp_info.set_property("cmake_file_name", "ComplexFileName1")

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    ConanFile.ref = Mock()
    conanfile_dep.ref.name = "OriginalDepName"
    conanfile_dep.ref.version = "1.0"
    conanfile_dep.package_folder = "/path/to/folder_dep"
    ConanFile.dependencies = Mock()
    conanfile.dependencies.transitive_host_requires = [ConanFileInterface(conanfile_dep)]
    conanfile.dependencies.host_requires = [ConanFileInterface(conanfile_dep)]

    cmakedeps = CMakeDeps(conanfile)
    files = cmakedeps.content
    assert "TARGET MySuperPkg1::MySuperPkg1" in files["ComplexFileName1Config.cmake"]
    assert 'set(MySuperPkg1_INCLUDE_DIRS_RELEASE "${MySuperPkg1_PACKAGE_FOLDER}/include")' \
           in files["ComplexFileName1-release-x86-data.cmake"]


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
    cpp_info.set_property("cmake_target_name", "GlobakPkgName1")
    cpp_info.components["mycomp"].set_property("cmake_target_name", "MySuperPkg1")
    cpp_info.set_property("cmake_file_name", "ComplexFileName1")

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    ConanFile.ref = Mock()
    conanfile_dep.ref.name = "OriginalDepName"
    conanfile_dep.ref.version = "1.0"
    conanfile_dep.package_folder = "/path/to/folder_dep"
    ConanFile.dependencies = Mock()
    conanfile.dependencies.transitive_host_requires = [ConanFileInterface(conanfile_dep)]
    conanfile.dependencies.host_requires = [ConanFileInterface(conanfile_dep)]

    cmakedeps = CMakeDeps(conanfile)
    files = cmakedeps.content
    assert "TARGET GlobakPkgName1::MySuperPkg1" in files["ComplexFileName1Config.cmake"]
    assert 'set(GlobakPkgName1_INCLUDE_DIRS_DEBUG "${GlobakPkgName1_PACKAGE_FOLDER}/include")' \
           in files["ComplexFileName1-debug-x64-data.cmake"]
    assert 'set(GlobakPkgName1_MySuperPkg1_INCLUDE_DIRS_DEBUG ' \
           '"${GlobakPkgName1_PACKAGE_FOLDER}/include")' \
           in files["ComplexFileName1-debug-x64-data.cmake"]


def test_cmake_deps_links_flags():
    # https://github.com/conan-io/conan/issues/8703
    ConanFile.dependencies = Mock()
    ConanFile.ref = Mock()
    conanfile = ConanFile(Mock(), None)
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]}), EnvValues())
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"
    conanfile.dependencies.transitive_host_requires = []
    conanfile.dependencies.host_requires = []

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.sharedlinkflags = ["/NODEFAULTLIB", "/OTHERFLAG"]
    cpp_info.exelinkflags = ["/OPT:NOICF"]
    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info

    conanfile_dep.ref.name = "mypkg"
    conanfile_dep.ref.version = "1.0"
    conanfile_dep.package_folder = "/path/to/folder_dep"
    conanfile.dependencies.transitive_host_requires = [ConanFileInterface(conanfile_dep)]
    conanfile.dependencies.host_requires = [ConanFileInterface(conanfile_dep)]

    cmakedeps = CMakeDeps(conanfile)
    files = cmakedeps.content
    data_cmake = files["mypkg-release-x86-data.cmake"]
    assert "set(mypkg_SHARED_LINK_FLAGS_RELEASE -NODEFAULTLIB;-OTHERFLAG)" in data_cmake
    assert "set(mypkg_EXE_LINK_FLAGS_RELEASE -OPT:NOICF)" in data_cmake
