import mock
from mock import Mock
import unittest

from mock.mock import MagicMock, PropertyMock
from conan.tools import qbs
from conan.tools.files.patches import patch

from conan.tools.qbs.qbsmoduletemplate import QbsModuleTemplate, DepsCppQbs
from conan.tools.qbs.qbsdeps import QbsDeps
import conan.tools.qbs.utils as utils


class StubCppInfo(object):
    includedirs = []
    libdirs = []
    system_libs = []
    libs = []
    frameworkdirs = []
    frameworks = []
    defines = []
    cflags = []
    cxxflags = []
    sharedlinkflags = []
    exelinkflags = []


class QbsModuleTemplateTest(unittest.TestCase):
    def test_suffix(self):
        qbs_deps = QbsDeps(None)
        template = QbsModuleTemplate(qbs_deps, None, Mock(), None)

        template.conanfile.is_build_context = False
        self.assertEqual(template.suffix, "")

        template.conanfile.is_build_context = True
        self.assertEqual(template.suffix, "")

        name = "foobar"
        expected_suffix = "-build"
        template.conanfile.ref.name = name
        qbs_deps.build_context_suffix["foobar"] = expected_suffix
        self.assertEqual(template.suffix, expected_suffix)

    def test_context(self):
        template = QbsModuleTemplate(None, None, Mock(), None)

        expected_pkg_version = "1.2.3"
        expected_cpp = DepsCppQbs(StubCppInfo(), "package")
        expected_dependencies = 42

        template.conanfile.ref.version = expected_pkg_version
        template.component_name = "comp_name"
        template.conanfile.cpp_info.components = {"comp_name": expected_cpp}
        template.conanfile.package_folder = "package"
        template.get_direct_dependencies = MagicMock(return_value=42)
        result = template.context

        self.assertEqual(result["pkg_version"], expected_pkg_version)
        self.assertEqual(result["cpp"], expected_cpp)
        self.assertEqual(result["dependencies"], expected_dependencies)

    def test_filename(self):
        expected_module_name = "module-name"
        expected_component_name = "comp_name"
        with mock.patch.object(QbsModuleTemplate, 'suffix',
                               new_callable=PropertyMock) as mock_suffix:
            mock_suffix.return_value = "_build"
            template = QbsModuleTemplate(None, None, Mock(), None)

            with mock.patch.object(utils, 'get_module_name',
                                   new_callable=MagicMock) as mock_module_name:
                # utils.get_module_name = MagicMock(return_value=expected_module_name)
                mock_module_name.return_value = expected_module_name
                template.conanfile.cpp_info.has_components = False
                self.assertEqual(template.filename, "{}{}".format(
                    expected_module_name, mock_suffix.return_value))

                template.component_name = expected_component_name
                template.conanfile.cpp_info.has_components = True
                self.assertEqual(template.filename,
                                 "{}{}/{}".format(expected_module_name,
                                                  mock_suffix.return_value,
                                                  expected_component_name))

    def test_get_direct_dependencies(self):
        name = "foobar"
        version = "1.2.3"

        with mock.patch.object(utils, 'get_component_name',
                               new_callable=MagicMock()) as mock_component_name:
            def component_name(component, default):
                del component
                return default

            mock_component_name.side_effect = component_name

            template = QbsModuleTemplate(None, None, Mock(), None)
            template.conanfile.ref.name = name
            template.conanfile.ref.version = version

            component = Mock()
            template.conanfile.cpp_info.components = {template.component_name: component}

            component.requires = ["comp1", "comp2"]
            direct_dependencies = template.get_direct_dependencies()
            self.assertEqual(direct_dependencies, {"{}.{}".format(
                name, "comp1"): version, "{}.{}".format(name, "comp2"): version})

            req_conanfile = Mock()
            req_conanfile.ref.name = "lib"
            req_conanfile.ref.version = "2.0.0"
            component.requires = ["{0}::{0}".format(req_conanfile.ref.name)]
            req_conanfile.cpp_info.has_components = False
            template.conanfile.dependencies.direct_host = {req_conanfile.ref.name: req_conanfile}
            direct_dependencies = template.get_direct_dependencies()
            self.assertEqual(direct_dependencies, {
                             req_conanfile.ref.name: req_conanfile.ref.version})

            req_conanfile = Mock()
            req_conanfile.ref.name = "lib2"
            req_conanfile.ref.version = "9.8.7"
            component.requires = ["{}::foo".format(
                req_conanfile.ref.name), "{}::bar".format(req_conanfile.ref.name)]
            req_conanfile.cpp_info.has_components = True
            template.conanfile.dependencies.direct_host = {req_conanfile.ref.name: req_conanfile}
            direct_dependencies = template.get_direct_dependencies()
            self.assertEqual(direct_dependencies, {
                             "{}.{}".format(req_conanfile.ref.name,
                                            "foo"): req_conanfile.ref.version,
                             "{}.{}".format(req_conanfile.ref.name,
                                            "bar"): req_conanfile.ref.version})

    def test_render(self):
        with mock.patch.object(QbsModuleTemplate, 'context',
                               new_callable=PropertyMock) as mock_context:
            mock_context.return_value = None
            template = QbsModuleTemplate(None, None, None, None)
            template.render()


class DepsCppQbsTest(unittest.TestCase):
    def test_init(self):
        package_folder = "package"

        cpp_info = StubCppInfo()
        cpp_info.includedirs = ["include", "include2"]
        cpp_info.libdirs = ["lib", "lib2"]
        cpp_info.system_libs = ["syslib", "syslib2"]
        cpp_info.libs = ["lib", "lib2"]
        cpp_info.frameworkdirs = ["frameworkdir", "frameworkdir2"]
        cpp_info.frameworks = ["framework", "framework2"]
        cpp_info.defines = ["define", "define2"]
        cpp_info.cflags = ["cflag", "cflag2"]
        cpp_info.cxxflags = ["cxxflag", "cxxflag2"]
        cpp_info.sharedlinkflags = ["sharedlinkflag", "sharedlinkflag2"]
        cpp_info.exelinkflags = ["exelinkflags", "exelinkflags2"]

        cpp_info_qbs = DepsCppQbs(cpp_info, package_folder)
        self.assertEqual(cpp_info_qbs.includedirs,
                         utils.prepend_package_folder(cpp_info.includedirs, package_folder))
        self.assertEqual(cpp_info_qbs.libdirs,
                         utils.prepend_package_folder(cpp_info.libdirs, package_folder))
        self.assertEqual(cpp_info_qbs.system_libs, cpp_info.system_libs)
        self.assertEqual(cpp_info_qbs.libs, cpp_info.libs)
        self.assertEqual(cpp_info_qbs.frameworkdirs,
                         utils.prepend_package_folder(cpp_info.frameworkdirs, package_folder))
        self.assertEqual(cpp_info_qbs.frameworks, cpp_info.frameworks)
        self.assertEqual(cpp_info_qbs.defines, cpp_info.defines)
        self.assertEqual(cpp_info_qbs.cflags, cpp_info.cflags)
        self.assertEqual(cpp_info_qbs.cxxflags, cpp_info.cxxflags)
        self.assertEqual(cpp_info_qbs.sharedlinkflags, cpp_info.sharedlinkflags)
        self.assertEqual(cpp_info_qbs.exelinkflags, cpp_info.exelinkflags)
