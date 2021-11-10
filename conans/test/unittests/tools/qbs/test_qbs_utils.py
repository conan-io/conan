import mock
import unittest

from mock.mock import MagicMock
import conan.tools.qbs.utils as utils


class QbsUtilsTest(unittest.TestCase):
    def test_get_component_name(self):
        default = "default"
        module_name = "module-name"

        component = MagicMock()
        component.get_property = MagicMock(return_value=None)

        self.assertEqual(utils.get_component_name(component, default), default)
        component.get_property.assert_called_once_with("qbs_module_name", "QbsDeps")

        component.get_property = MagicMock(return_value=module_name)
        self.assertEqual(utils.get_component_name(component, default), module_name)
        component.get_property.assert_called_once_with("qbs_module_name", "QbsDeps")

    def test_get_module_name(self):
        dependency = MagicMock()
        dependency.cpp_info.get_property = 1
        dependency.ref.name = 2
        expected_result = 3

        utils.get_component_name = MagicMock(return_value=expected_result)
        self.assertEqual(utils.get_module_name(dependency), expected_result)
        utils.get_component_name.assert_called_once_with(dependency.cpp_info, dependency.ref.name)

    def test_prepend_package_folder(self):
        package_folder = "package"
        paths = ["a", "b", "c"]
        expected_paths = ["package/a", "package/b", "package/c"]

        prepended_paths = utils.prepend_package_folder(paths, package_folder)
        self.assertEqual(prepended_paths, expected_paths)
