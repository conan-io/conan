import mock
from mock import Mock

from conan.tools.b2 import B2Deps
from conan import ConanFile
from conans.model.build_info import CppInfo
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import ConanFileDependencies
from conans.model.recipe_ref import RecipeReference
from conans.model.requires import Requirement
from conans.model.settings import Settings


def test_cpp_info_name_b2deps():
    conanfile = ConanFile()
    conanfile._conan_node = Mock()
    conanfile._conan_node.context = "host"
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = Settings({
        "os": ["Windows"],
        "compiler": ["gcc"],
        "build_type": ["Release"],
        "arch": ["x86"]})
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"

    cpp_info = CppInfo(set_defaults=True)

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("OriginalDepName/1.0")
    conanfile_dep._conan_node.context = "host"
    conanfile_dep.settings = conanfile.settings
    conanfile_dep.folders.set_base_package("/path/to/folder_dep")
    # necessary, as the interface doesn't do it now automatically
    conanfile_dep.cpp_info.set_relative_base_folder("/path/to/folder_dep")

    # FIXME: This will run infinite loop if conanfile.dependencies.host.topological_sort.
    #  Move to integration test
    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({
            req: ConanFileInterface(conanfile_dep)})

        b2deps = B2Deps(conanfile)
        files = b2deps.content
        for k in sorted(files.keys()):
            print("\n\n{}:\n---\n{}\n---".format(k, files[k]))
        variation_filename = B2Deps._conanbuildinfo_variation_jam("originaldepname", conanfile.settings)
        assert "conanbuildinfo.jam" in files
        assert variation_filename in files
        variation_file = files[variation_filename]
        assert 'pkg-project originaldepname ;' in variation_file
        assert 'pkg-alias originaldepname//originaldepname' in variation_file
        assert '<architecture>x86' in variation_file
        assert '<variant>release' in variation_file
