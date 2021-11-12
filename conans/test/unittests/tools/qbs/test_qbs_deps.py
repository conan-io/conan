from mock import Mock
import mock
import unittest

from mock.mock import MagicMock, PropertyMock

from conan.tools.qbs.qbsdeps import QbsDeps
from conan.tools.qbs.qbsmoduletemplate import QbsModuleTemplate
from conan.tools.qbs.qbsconanmoduleproviderinfotemplate import QbsConanModuleProviderInfoTemplate
from conans import ConanFile
from conans.model.dependencies import Requirement
from conans.errors import ConanException


class QbsDepsTest(unittest.TestCase):
    @property
    def requires(self):
        requires = {
            "foo": Requirement(ConanFile(Mock(), None)),
            "bar": Requirement(ConanFile(Mock(), None)),
            "foobar": Requirement(ConanFile(Mock(), None))
        }
        for k, v in requires.items():
            v.ref.name = k
        return requires

    def test_activated_build_requires(self):
        build_requires = self.requires

        qbs_deps = QbsDeps(ConanFile(Mock(), None))

        activated_br = qbs_deps._activated_build_requires(build_requires)
        self.assertEqual(activated_br, set())

        qbs_deps.build_context_activated.append("foo")
        activated_br = qbs_deps._activated_build_requires(build_requires)
        self.assertEqual(activated_br, {"foo"})

        qbs_deps.build_context_activated.append("foobar")
        activated_br = qbs_deps._activated_build_requires(build_requires)
        self.assertEqual(activated_br, {"foo", "foobar"})

    def test_check_if_build_require_suffix_is_missing(self):
        qbs_deps = QbsDeps(ConanFile(Mock(), None))

        qbs_deps._activated_build_requires = MagicMock(return_value={})
        qbs_deps._check_if_build_require_suffix_is_missing(self.requires, dict())
        qbs_deps._activated_build_requires.assert_called_once_with(dict())

        qbs_deps._activated_build_requires = MagicMock(return_value={})
        qbs_deps._check_if_build_require_suffix_is_missing(self.requires, self.requires)
        qbs_deps._activated_build_requires.assert_called_once_with(self.requires)

        qbs_deps._activated_build_requires = MagicMock(return_value={"foobar"})
        with self.assertRaises(ConanException):
            qbs_deps._check_if_build_require_suffix_is_missing(
                self.requires, self.requires)
        qbs_deps._activated_build_requires.assert_called_once_with(self.requires)

        qbs_deps._activated_build_requires = MagicMock(return_value={"foobar"})
        qbs_deps.build_context_suffix["foobar"] = "build-foobar"
        qbs_deps._check_if_build_require_suffix_is_missing(self.requires, self.requires)
        qbs_deps._activated_build_requires.assert_called_once_with(self.requires)

    def test_get_conan_module_provider_info(self):
        qbs_deps = QbsDeps(ConanFile(Mock(), None))
        module_provider_info_template_content = "Hello World"
        module_provider_info_template = QbsConanModuleProviderInfoTemplate(None, None, None)
        module_provider_info_template.render = MagicMock(
            return_value=module_provider_info_template_content)
        qbs_deps._create_module_provider_info_template = MagicMock(
            return_value=module_provider_info_template)
        result = qbs_deps._get_conan_module_provider_info(None, None)
        self.assertEqual(
            result, {"qbs_conan-moduleprovider_info.json": module_provider_info_template_content})
        module_provider_info_template.render.assert_called_once_with()

    def test_get_module(self):
        file_content = "this is file content"
        file_name = "this is file name"
        module_file_name = "modules/{}/module.qbs".format(file_name)

        qbs_deps = QbsDeps(ConanFile(Mock(), None))
        with mock.patch.object(QbsModuleTemplate, 'filename',
                               new_callable=PropertyMock) as mock_filename:
            module_template = QbsModuleTemplate(None, None, None, None)

            module_template.render = MagicMock(return_value=file_content)
            mock_filename.return_value = file_name
            qbs_deps._create_module_template = MagicMock(return_value=module_template)

            require = 1
            dep = 2
            comp_name = 3

            result = qbs_deps._get_module(require, dep, comp_name)
            self.assertEqual(result, {module_file_name: file_content})
            qbs_deps._create_module_template.assert_called_once_with(require, dep, comp_name)
            module_template.render.assert_called_once_with()
            mock_filename.assert_called_once_with()

    def test_content(self):
        min_result = {"qbs_conan-moduleprovider_info.json": "module provider info"}
        qbs_deps = QbsDeps(Mock())
        qbs_deps.build_context_activated.append("foobar")
        host_req = dict()
        build_req = dict()
        test_req = dict()

        def setup_mocks():
            qbs_deps._check_if_build_require_suffix_is_missing = MagicMock()
            qbs_deps._get_module = MagicMock()
            qbs_deps._get_conan_module_provider_info = MagicMock(return_value=min_result)
            qbs_deps._conanfile.dependencies.host = host_req
            qbs_deps._conanfile.dependencies.direct_build = build_req
            qbs_deps._conanfile.dependencies.test = test_req

        setup_mocks()
        self.assertEqual(qbs_deps.content, min_result)
        qbs_deps._check_if_build_require_suffix_is_missing.assert_called_once_with(
            host_req, build_req)
        qbs_deps._get_conan_module_provider_info.assert_called_once_with([], [])

        def make_dep(name, version, build_context=False, skip=False, component_names=[]):
            dep = Mock()
            dep.ref.name = name
            dep.ref.version = version
            dep.is_build_context = build_context
            dep.cpp_info.get_property = MagicMock(return_value=skip)
            dep.cpp_info.has_components = component_names != []
            dep.cpp_info.component_names = component_names
            dep.skip = skip
            return dep

        def skip(dep):
            return dep.skip or dep.is_build_context and dep.ref.name not in qbs_deps.build_context_activated

        host_req = {1: make_dep("foo", "1.2.3"), 2: make_dep(
            "bar", "9.8.7", skip=True), 3: make_dep("not_me", "0.0.0", build_context=True),
            4: make_dep("foobar", "5.5.5", build_context=True),
            5: make_dep("with_comp", "1.1.1", component_names=["comp1", "comp2"])}
        content = min_result
        content.update({"foo": "1.2.3", "bar": "9.8.7"})
        setup_mocks()
        self.assertEqual(qbs_deps.content, content)
        qbs_deps._check_if_build_require_suffix_is_missing.assert_called_once_with(
            host_req, build_req)
        for r, d in host_req.items():
            if not skip(d):
                if d.cpp_info.has_components:
                    for comp_name in d.cpp_info.component_names:
                        qbs_deps._get_module.assert_any_call(r, d, comp_name)
                else:
                    qbs_deps._get_module.assert_any_call(r, d, None)
        qbs_deps._get_conan_module_provider_info.assert_called_once_with(
            [r for r, d in host_req.items() if not skip(d)],
            [d for r, d in host_req.items() if not skip(d)])
