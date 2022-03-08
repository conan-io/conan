import mock
from mock import Mock
import re

from conan.tools.google import BazelDeps
from conan import ConanFile
from conans.model.conanfile_interface import ConanFileInterface

from conans.model.dependencies import ConanFileDependencies
from conans.model.build_info import CppInfo
from conans.model.recipe_ref import RecipeReference
from conans.model.requires import Requirement


def test_bazeldeps_main_buildfile():
    expected_content = [
        'def load_conan_dependencies():',
        'native.new_local_repository(',
        'name="OriginalDepName",',
        'path="/path/to/folder_dep",',
        'build_file="conandeps/OriginalDepName/BUILD",'
    ]

    conanfile = ConanFile(None)

    cpp_info = CppInfo(set_defaults=True)

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("OriginalDepName/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("OriginalDepName/1.0"))
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
    conanfile = ConanFile()

    conanfile_dep = ConanFile()
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("OriginalDepName/1.0")
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")

    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("OriginalDepName/1.0"), build=True)
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        bazeldeps = BazelDeps(conanfile)

        for build_dependency in bazeldeps._conanfile.dependencies.direct_build.values():
            dependency_content = bazeldeps._get_build_dependency_buildfile_content(build_dependency)
            assert 'filegroup(\n    name = "OriginalDepName_binaries",' in dependency_content
            assert 'data = glob(["**"]),' in dependency_content
