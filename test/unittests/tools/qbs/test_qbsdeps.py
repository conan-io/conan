import mock
from mock import Mock

from conan.tools.qbs import QbsDeps
from conan import ConanFile
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.dependencies import ConanFileDependencies
from conans.model.build_info import CppInfo
from conans.model.recipe_ref import RecipeReference
from conans.model.requires import Requirement
from conans.model.settings import Settings


def test_content_qbsdeps():
    conanfile = ConanFile()
    conanfile._conan_node = Mock()
    conanfile._conan_node.context = "host"
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]})
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"
    conanfile.settings.compiler = "gcc"
    conanfile.settings.os = "Windows"
    from conan.tools.env import Environment
    conanfile._conan_buildenv = Environment()
    conanfile._conan_buildenv.define("MyVar", "MyValue")

    cpp_info = CppInfo(set_defaults=True)

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("OriginalDepName/1.0")
    conanfile_dep._conan_node.context = "host"
    conanfile_dep.settings = conanfile.settings

    # TODO: this loops e.g. with VirtualBuildEnv
    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        qbsdeps = QbsDeps(conanfile)
        files = qbsdeps.content

        assert 'common.json' in files
        assert 'modules/OriginalDepName.json' in files
        # common_content = files['common.json'].get_content()
        # assert 'MyValue' == common_content.get('build_env').get('MyVar')
        # assert 1 == common_content.get('format_version')
        module_content = files['modules/OriginalDepName.json'].get_content()

        assert 'OriginalDepName' == module_content.get('package_name')
        assert '1.0' == module_content.get('version')
        assert 'settings' in module_content
        assert 'Release' == module_content.get('settings').get('build_type')
        assert 'gcc' == module_content.get('settings').get('compiler')
        assert 'x86' == module_content.get('settings').get('arch')
        assert 'Windows' == module_content.get('settings').get('os')
        # we patch all instances, can we avoid that in the dep?
        module_dep = {'name': 'OriginalDepName', 'version': '1.0'}
        assert [module_dep] == module_content.get('dependencies')
        assert 'cpp_info' in module_content
        assert 'includedirs' in module_content['cpp_info']
        assert 'libdirs' in module_content['cpp_info']


def test_cpp_info_name_qbsdeps():
    conanfile = ConanFile()
    conanfile._conan_node = Mock()
    conanfile._conan_node.context = "host"
    conanfile.settings = "os", "compiler", "build_type", "arch"
    conanfile.settings = Settings({"os": ["Windows"],
                                   "compiler": ["gcc"],
                                   "build_type": ["Release"],
                                   "arch": ["x86"]})
    conanfile.settings.build_type = "Release"
    conanfile.settings.arch = "x86"

    cpp_info = CppInfo(set_defaults=True)
    cpp_info.set_property("pkg_config_name", "MySuperPkg1")

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("OriginalDepName/1.0")
    conanfile_dep._conan_node.context = "host"
    conanfile_dep.settings = conanfile.settings

    with mock.patch('conan.ConanFile.dependencies', new_callable=mock.PropertyMock) as mock_deps:
        req = Requirement(RecipeReference.loads("OriginalDepName/1.0"))
        mock_deps.return_value = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})

        qbsdeps = QbsDeps(conanfile)
        files = qbsdeps.content

        assert 'common.json' in files
        assert 'modules/MySuperPkg1.json' in files
