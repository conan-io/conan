import mock
from mock import Mock

from conan.tools.google import BazelDeps
from conans import ConanFile
from conans.model.build_info import CppInfo
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.ref import ConanFileReference


def test_bazeldeps_dependency_buildfiles():
    conanfile = ConanFile(Mock(), None)

    cpp_info = CppInfo("mypkg", "dummy_root_folder1")

    conanfile_dep = ConanFile(Mock(), None)
    conanfile_dep.cpp_info = cpp_info

    with mock.patch('conans.ConanFile.ref', new_callable=mock.PropertyMock) as mock_ref:
        with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
            mock_ref.return_value = ConanFileReference.loads("OriginalDepName/1.0")
            mock_deps.return_value = Mock()

            conanfile_dep.package_folder = "/path/to/folder_dep"
            conanfile.dependencies.transitive_host_requires = [ConanFileInterface(conanfile_dep)]
            conanfile.dependencies.host_requires = [ConanFileInterface(conanfile_dep)]

            bazeldeps = BazelDeps(conanfile)

            for dependency in bazeldeps._conanfile.dependencies.transitive_host_requires:
                dependency_content = bazeldeps._get_dependency_buildfile_content(dependency)
                assert 'cc_library(\n    name = "OriginalDepName",' in dependency_content


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

    with mock.patch('conans.ConanFile.ref', new_callable=mock.PropertyMock) as mock_ref:
        with mock.patch('conans.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
            mock_ref.return_value = ConanFileReference.loads("OriginalDepName/1.0")
            mock_deps.return_value = Mock()

            conanfile_dep.package_folder = "/path/to/folder_dep"
            conanfile.dependencies.transitive_host_requires = [ConanFileInterface(conanfile_dep)]
            conanfile.dependencies.host_requires = [ConanFileInterface(conanfile_dep)]

            bazeldeps = BazelDeps(conanfile)

            local_repositories = []
            for dependency in bazeldeps._conanfile.dependencies.transitive_host_requires:
                content = bazeldeps._create_new_local_repository(dependency, "conandeps/OriginalDepName/BUILD")
                local_repositories.append(content)

            content = bazeldeps._get_main_buildfile_content(local_repositories)

            for line in expected_content:
                assert line in content
