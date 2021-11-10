from mock import Mock
import unittest

from mock.mock import MagicMock

from conan.tools.qbs.qbsdeps import QbsDeps
from conan.tools.qbs.qbsmoduletemplate import QbsModuleTemplate
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

    def test_get_module(self):
        qbs_deps = QbsDeps(ConanFile(Mock(), None))
        module_template = QbsModuleTemplate(None, None, None, None)

        file_content = "this is file content"
        file_name = "this is file name"
        module_file_name = "modules/{}/module.qbs".format(file_name)

        module_template.render = MagicMock(return_value=file_content)
        module_template.filename = MagicMock(return_value=file_name)
        qbs_deps._create_module_template = MagicMock(return_value=module_template)

        require = 1
        dep = 2
        comp_name = 3

        result = qbs_deps._get_module(require, dep, comp_name)
        qbs_deps._create_module_template.assert_called_once_with(require, dep, comp_name)
        module_template.render.assert_called_once()
        module_template.filename.assert_called_once()
