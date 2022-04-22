import os
import re
import platform

import mock
from mock import Mock

from conan.tools.google import BazelDeps
from conans import ConanFile
from conans.model.build_info import CppInfo
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import Requirement, ConanFileDependencies
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_bazeldeps_dependency_buildfiles():
    conanfile = ConanFile(Mock(), None)

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info.system_libs = ["system_lib1"]
    cpp_info.libs = ["lib1"]

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    package_folder = temp_folder()
    save(os.path.join(package_folder, "lib", "liblib1.a"), "")
    conanfile_dep.folders.set_base_package(package_folder)

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        for dependency in bazeldeps._conanfile.dependencies.host.values():
            dependency_content = bazeldeps._get_dependency_buildfile_content(dependency)
            assert 'cc_library(\n    name = "OriginalDepName",' in dependency_content
            assert """defines = ["DUMMY_DEFINE=\\\\\\"string/value\\\\\\""]""" in dependency_content
            if platform.system() == "Windows":
                assert 'linkopts = ["/DEFAULTLIB:system_lib1"]' in dependency_content
            else:
                assert 'linkopts = ["-lsystem_lib1"],' in dependency_content
            assert 'deps = [\n    \n    ":lib1_precompiled",' in dependency_content


def test_bazeldeps_dependency_transitive():
    # Create main ConanFile
    conanfile = ConanFile(Mock(), None)

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")
    cpp_info.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info.system_libs = ["system_lib1"]
    cpp_info.libs = ["lib1"]

    # Create a ConanFile for a direct dependency
    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    package_folder = temp_folder()
    save(os.path.join(package_folder, "lib", "liblib1.a"), "")
    conanfile_dep.folders.set_base_package(package_folder)

    # Add dependency on the direct dependency
    req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
    conanfile._conan_dependencies = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

    cpp_info_transitive = CppInfo("mypkg_t", "dummy_root_folder1")
    cpp_info_transitive.defines = ["DUMMY_DEFINE=\"string/value\""]
    cpp_info_transitive.system_libs = ["system_lib1"]
    cpp_info_transitive.libs = ["lib_t1"]

    # Create a ConanFile for a transitive dependency
    conanfile_dep_transitive = ConanFile(Mock(), None)
    conanfile_dep_transitive.cpp_info = cpp_info_transitive
    conanfile_dep_transitive._conan_node = Mock()
    conanfile_dep_transitive._conan_node.ref = ConanFileReference.loads("TransitiveDepName/1.0")
    conanfile_dep_transitive.folders.set_base_package("/path/to/folder_dep_t")

    # Add dependency from the direct dependency to the transitive dependency
    req = Requirement(ConanFileReference.loads("TransitiveDepName/1.0"))
    conanfile_dep._conan_dependencies = ConanFileDependencies(
        {req: ConanFileInterface(conanfile_dep_transitive)})

    bazeldeps = BazelDeps(conanfile)

    for dependency in bazeldeps._conanfile.dependencies.host.values():
        dependency_content = bazeldeps._get_dependency_buildfile_content(dependency)
        assert 'cc_library(\n    name = "OriginalDepName",' in dependency_content
        assert 'defines = ["DUMMY_DEFINE=\\\\\\"string/value\\\\\\""],' in dependency_content
        if platform.system() == "Windows":
            assert 'linkopts = ["/DEFAULTLIB:system_lib1"],' in dependency_content
        else:
            assert 'linkopts = ["-lsystem_lib1"],' in dependency_content

        # Ensure that transitive dependency is referenced by the 'deps' attribute of the direct
        # dependency
        assert re.search(r'deps =\s*\[\s*":lib1_precompiled",\s*"@TransitiveDepName"',
                         dependency_content)


def test_bazeldeps_interface_buildfiles():
    conanfile = ConanFile(Mock(), None)

    cpp_info = CppInfo("mypkg", "dummy_root_folder2")

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep.folders.set_base_package(temp_folder())
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/2.0")

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        dependency = next(iter(bazeldeps._conanfile.dependencies.host.values()))
        dependency_content = re.sub(r"\s", "", bazeldeps._get_dependency_buildfile_content(dependency))
        assert(dependency_content == 'load("@rules_cc//cc:defs.bzl","cc_import","cc_library")cc_library(name="OriginalDepName",hdrs=glob(["include/**"]),includes=["include"],visibility=["//visibility:public"],)')


def test_bazeldeps_main_buildfile():
    expected_content = [
        'def load_conan_dependencies():',
        'native.new_local_repository(',
        'name="OriginalDepName",',
        'path="/path/to/folder_dep",',
        'build_file="conandeps/OriginalDepName/BUILD",'
    ]

    conanfile = ConanFile(Mock(), None)

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        local_repositories = []
        for dependency in bazeldeps._conanfile.dependencies.host.values():
            content = bazeldeps._create_new_local_repository(dependency,
                                                             "conandeps/OriginalDepName/BUILD")
            local_repositories.append(content)

        content = bazeldeps._get_main_buildfile_content(local_repositories)

        for line in expected_content:
            assert line in content

def test_bazeldeps_build_dependency_buildfiles():
    conanfile = ConanFile(Mock(), None)

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = ConanFileReference.loads("OriginalDepName/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(ConanFileReference.loads("OriginalDepName/1.0"), build=True)
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        for build_dependency in bazeldeps._conanfile.dependencies.direct_build.values():
            dependency_content = bazeldeps._get_build_dependency_buildfile_content(build_dependency)
            assert 'filegroup(\n    name = "OriginalDepName_binaries",' in dependency_content
            assert 'data = glob(["**"]),' in dependency_content
