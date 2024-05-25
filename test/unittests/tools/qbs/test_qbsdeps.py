import mock
from mock import Mock

from conan.tools.qbs import QbsDeps
from conan import ConanFile
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.conf import ConfDefinition
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
    conanfile.settings_build = conanfile.settings
    conanfile.conf = ConfDefinition()
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
    conanfile_dep._conan_dependencies = ConanFileDependencies({})
    conanfile_dep._conan_node.transitive_deps = {}

    req = Requirement(RecipeReference.loads("OriginalDepName/1.0"))
    conanfile._conan_dependencies = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})
    conanfile._conan_node.transitive_deps = {}

    qbsdeps = QbsDeps(conanfile)
    files = qbsdeps.content

    assert 'OriginalDepName.json' in files
    module_content = files['OriginalDepName.json'].get_content()
    assert 'MyValue' == module_content.get('build_env').get('MyVar')

    assert 'OriginalDepName' == module_content.get('package_name')
    assert '1.0' == module_content.get('version')
    assert 'settings' in module_content
    assert 'Release' == module_content.get('settings').get('build_type')
    assert 'gcc' == module_content.get('settings').get('compiler')
    assert 'x86' == module_content.get('settings').get('arch')
    assert 'Windows' == module_content.get('settings').get('os')
    assert [] == module_content.get('dependencies')
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
    conanfile.settings.os = "Windows"
    conanfile.settings_build = conanfile.settings
    conanfile.conf = ConfDefinition()
    from conan.tools.env import Environment
    conanfile._conan_buildenv = Environment()

    cpp_info = CppInfo(set_defaults=True)
    cpp_info.set_property("pkg_config_name", "MySuperPkg1")

    conanfile_dep = ConanFile(None)
    conanfile_dep.cpp_info = cpp_info
    conanfile_dep._conan_node = Mock()
    conanfile_dep._conan_node.ref = RecipeReference.loads("OriginalDepName/1.0")
    conanfile_dep._conan_node.context = "host"
    conanfile_dep.settings = conanfile.settings

    conanfile_dep._conan_dependencies = ConanFileDependencies({})
    conanfile_dep._conan_node.transitive_deps = {}

    req = Requirement(RecipeReference.loads("OriginalDepName/1.0"))
    conanfile._conan_dependencies = ConanFileDependencies({req: ConanFileInterface(conanfile_dep)})
    conanfile._conan_node.transitive_deps = {}

    qbsdeps = QbsDeps(conanfile)
    files = qbsdeps.content

    assert 'MySuperPkg1.json' in files
