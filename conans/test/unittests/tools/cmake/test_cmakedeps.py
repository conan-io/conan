import mock
from mock import Mock

from conan.tools.cmake import CMakeDeps
from conans import ConanFile, Settings
from conans.model.build_info import CppInfo
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import ConanFileDependencies, Requirement
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference


def test_cpp_info_name_cmakedeps():
    conanfile = ConanFile(Mock(), None)
    conanfile._conan_node = Mock()
    conanfile._conan_node.context = "host"
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]}), EnvValues())
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.set_property("cmake_target_name", "MySuperPkg1::MySuperPkg1")
    cpp_info.set_property("cmake_file_name", "ComplexFileName1")

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    conanfile_dep._conan_node.context = "host"
    conanfile_dep.settings = conanfile.settings
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        cmakedeps = CMakeDeps(conanfile)
        files = cmakedeps.content
        assert "TARGET MySuperPkg1::MySuperPkg1" in files["ComplexFileName1-Target-release.cmake"]
        assert 'set(OriginalDepName_INCLUDE_DIRS_RELEASE ' \
               '"${OriginalDepName_PACKAGE_FOLDER_RELEASE}/include")' \
               in files["ComplexFileName1-release-x86-data.cmake"]


def test_cpp_info_name_cmakedeps_components():
    conanfile = ConanFile(Mock(), None)
    conanfile._conan_node = Mock()
    conanfile._conan_node.context = "host"
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release", "Debug"],
                                   "arch": ["x86", "x64"]}), EnvValues())
    conanfile.settings.build_type = "Debug"
    conanfile.settings.arch = "x64"

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.set_property("cmake_target_name", "GlobalPkgName1::GlobalPkgName1")
    cpp_info.components["mycomp"].set_property("cmake_target_name", "GlobalPkgName1::MySuperPkg1")
    cpp_info.set_property("cmake_file_name", "ComplexFileName1")

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep.settings = conanfile.settings
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    conanfile_dep._conan_node.context = "host"
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        cmakedeps = CMakeDeps(conanfile)
        files = cmakedeps.content
        assert "TARGET GlobalPkgName1::MySuperPkg1" in files["ComplexFileName1-Target-debug.cmake"]
        # Global variables for the packages
        # https://github.com/conan-io/conan/issues/11862
        assert 'set(OriginalDepName_INCLUDE_DIRS_DEBUG ' \
               '"${OriginalDepName_PACKAGE_FOLDER_DEBUG}/include")' \
               in files["ComplexFileName1-debug-x64-data.cmake"]
        # AND components
        assert 'set(OriginalDepName_GlobalPkgName1_MySuperPkg1_INCLUDE_DIRS_DEBUG ' \
               '"${OriginalDepName_PACKAGE_FOLDER_DEBUG}/include")' \
               in files["ComplexFileName1-debug-x64-data.cmake"]


def test_cmake_deps_links_flags():
    # https://github.com/conan-io/conan/issues/8703
    conanfile = ConanFile(Mock(), None)
    conanfile._conan_node = Mock()
    conanfile._conan_node.context = "host"
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]}), EnvValues())
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    # https://github.com/conan-io/conan/issues/8811 regression, fix with explicit - instead of /
    cpp_info.sharedlinkflags = ["-NODEFAULTLIB", "-OTHERFLAG"]
    cpp_info.exelinkflags = ["-OPT:NOICF"]
    cpp_info.objects = ["myobject.o"]
    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep.settings = conanfile.settings
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("mypkg/1.0")
    conanfile_dep._conan_node.context = "host"
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        cmakedeps = CMakeDeps(conanfile)
        files = cmakedeps.content
        data_cmake = files["mypkg-release-x86-data.cmake"]
        assert 'set(mypkg_SHARED_LINK_FLAGS_RELEASE "-NODEFAULTLIB;-OTHERFLAG")' in data_cmake
        assert 'set(mypkg_EXE_LINK_FLAGS_RELEASE "-OPT:NOICF")' in data_cmake
        assert 'set(mypkg_OBJECTS_RELEASE "${mypkg_PACKAGE_FOLDER_RELEASE}/myobject.o")' \
               in data_cmake


def test_component_name_same_package():
    """
    When the package and the component are the same the variables declared in data and linked
    to the target have to be the same.
    https://github.com/conan-io/conan/issues/9071"""
    conanfile = ConanFile(Mock(), None)
    conanfile._conan_node = Mock()
    conanfile._conan_node.context = "host"
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.initialize(Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]}), EnvValues())
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")

    # We adjust the component with the same name as the package on purpose
    cpp_info.components["mypkg"].includedirs = ["includedirs1"]

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep.settings = conanfile.settings
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.context = "host"
    conanfile_dep._conan_node.ref = ConanFileReference.loads("mypkg/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("mypkg/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        cmakedeps = CMakeDeps(conanfile)
        files = cmakedeps.content
        target_cmake = files["mypkg-Target-release.cmake"]
        assert "$<$<CONFIG:Release>:${mypkg_mypkg_mypkg_INCLUDE_DIRS_RELEASE}> APPEND)" \
               in target_cmake

        data_cmake = files["mypkg-release-x86-data.cmake"]
        assert 'set(mypkg_mypkg_mypkg_INCLUDE_DIRS_RELEASE ' \
               '"${mypkg_PACKAGE_FOLDER_RELEASE}/includedirs1")' in data_cmake
