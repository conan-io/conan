import json
import mock
import unittest

from mock.mock import MagicMock, Mock
from conan.tools.qbs.qbsconanmoduleproviderinfotemplate import QbsConanModuleProviderInfoTemplate

import conan.tools.qbs.utils as utils


class TestQbsModuleProviderInfoTemplate(unittest.TestCase):
    def test_create_component(self):
        with mock.patch.object(utils, 'get_component_name',
                               new_callable=MagicMock) as mock_get_component_name:
            with mock.patch.object(utils, 'prepend_package_folder',
                                   new_callable=MagicMock) as mock_prepend_package_folder:
                template = QbsConanModuleProviderInfoTemplate(None, None, None)

                dep = Mock()
                dep.package_folder = "package"
                component = Mock()
                component.bindirs = ["bin", "bin2", "hello"]
                expected_bindirs = [
                    "{}/{}".format(dep.package_folder, d) for d in component.bindirs]
                mock_prepend_package_folder.return_value = expected_bindirs
                comp = template.create_component(dep, component, None)
                self.assertEqual(
                    comp, {"name": None, "bindirs": mock_prepend_package_folder.return_value})
                mock_prepend_package_folder.assert_called_once_with(
                    component.bindirs, dep.package_folder)
                mock_get_component_name.assert_not_called()
                mock_prepend_package_folder.reset_mock()

                comp_name = "comp"
                mock_prepend_package_folder.return_value = expected_bindirs
                expected_name = "some comp name"
                mock_get_component_name.return_value = expected_name
                comp = template.create_component(dep, component, comp_name)
                self.assertEqual(comp, {"name": expected_name, "bindirs": expected_bindirs})
                mock_get_component_name.assert_called_once_with(component, comp_name)
                mock_prepend_package_folder.assert_called_once_with(
                    component.bindirs, dep.package_folder)

    def test_render(self):
        def create_dep(name, build_env=dict(), run_env=dict(), component_names=[]):
            dep = Mock()
            dep.buildenv_info.vars = MagicMock(return_value=build_env)
            dep.runenv_info.vars = MagicMock(return_value=run_env)
            dep.ref.name = name
            dep.cpp_info.has_components = component_names != []
            dep.cpp_info.component_names = component_names
            dep.cpp_info.components = {comp_name: None for comp_name in component_names}
            return dep

        def create_env(num, s):
            return {"{}_{}_key_{}".format(num, s, i): "{}_value_{}".format(num, i) for i in range(0, 5)}

        def create_component_names(num):
            return ["{}_comp_{}".format(num, i) for i in range(0, 4)]

        def side_effect_create_component(dep, component, comp_name):
            del component
            return "created_component-{}".format(comp_name
                                                 if comp_name
                                                 else dep.ref.name)

        def create_deps_env_info(vars):
            deps_env_info = Mock()
            deps_env_info.vars = vars
            return deps_env_info

        def side_effect_get_module_name(dep):
            return dep.ref.name

        def side_effect_json_dumps(info, indent):
            del indent
            return info

        with mock.patch.object(utils, 'get_module_name',
                               new_callable=MagicMock) as mock_get_module_name:
            mock_get_module_name.side_effect = side_effect_get_module_name
            with mock.patch.object(json, 'dumps', new_callable=MagicMock) as mock_json_dump:
                mock_json_dump.side_effect = side_effect_json_dumps

                template = QbsConanModuleProviderInfoTemplate(Mock(), Mock(), Mock())
                template.create_component = MagicMock()
                template.create_component.side_effect = side_effect_create_component
                template.qbsdeps._conanfile.deps_env_info = {
                    "lib0": create_deps_env_info(create_env(0, 'd')),
                    "lib1": create_deps_env_info(create_env(1, 'd')),
                    "lib2": create_deps_env_info(create_env(2, 'd'))
                }

                template.dependencies = [create_dep("lib{}".format(i),
                                                    create_env(i, 'b'),
                                                    create_env(i, 'r'),
                                                    create_component_names(i) if i % 2 else [])
                                         for i in range(0, 3)]

                expected_info = [
                    {
                        "name": "lib0",
                        "env": {
                            "build": create_env(0, 'b'),
                            "run": create_env(0, 'r'),
                            "deps": create_env(0, 'd')
                        },
                        "components": ["created_component-lib0"]
                    },
                    {
                        "name": "lib1",
                        "env": {
                            "build": create_env(1, 'b'),
                            "run": create_env(1, 'r'),
                            "deps": create_env(1, 'd')
                        },
                        "components": ["created_component-{}".format(comp_name)
                                       for comp_name in create_component_names(1)]
                    },
                    {
                        "name": "lib2",
                        "env": {
                            "build": create_env(2, 'b'),
                            "run": create_env(2, 'r'),
                            "deps": create_env(2, 'd')
                        },
                        "components": ["created_component-lib2"]
                    }
                ]
                info = template.render()
                self.assertEqual(info, expected_info)
