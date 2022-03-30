import unittest

import six

import conan.tools.qbs.qbs as qbs

from conans.client import tools
from conans.errors import ConanException
from conans.test.utils.mocks import MockConanfile, MockSettings
from conans.test.utils.test_files import temp_folder


class RunnerMock(object):
    def __init__(self, return_ok=True, output=None):
        self.command_called = None
        self.return_ok = return_ok
        self.output = output

    def __call__(self, command, output, win_bash=False, subsystem=None):
        self.command_called = command
        self.win_bash = win_bash
        self.subsystem = subsystem
        if self.output and output and hasattr(output, 'write'):
            output.write(self.output)
        return 0 if self.return_ok else 1


class QbsTest(unittest.TestCase):
    def test_generating_config_command_line(self):
        name = 'default'
        flag_dict = {
            'modules.cpp.cxxFlags': ['-frtti', '-fexceptions'],
            'modules.cpp.ldFlags': '--defsym=hello_world',
            'products.App.myIntProperty': 13,
            'products.App.myBoolProperty': True
        }
        expected_config_line = [
            'config:%s' % name,
        ]
        for key, value in flag_dict.items():
            if type(value) is bool:
                if value:
                    value = 'true'
                else:
                    value = 'false'
            expected_config_line.append('%s:%s' % (key, value))
        self.assertEqual(
            qbs._configuration_dict_to_commandlist(name, flag_dict),
            expected_config_line)

    def test_construct_build_helper_without_project_file(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}))
        conanfile.folders.set_base_source('.')
        build_helper = qbs.Qbs(conanfile)
        self.assertEqual(build_helper.jobs, tools.cpu_count())
        self.assertEqual(build_helper._project_file, conanfile.source_folder)

    def test_construct_build_helper_with_project_file(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}))
        # just asume that the test is called from repo root
        profile_file_path = temp_folder()
        build_helper = qbs.Qbs(conanfile, project_file=profile_file_path)
        self.assertEqual(build_helper._project_file, profile_file_path)

    def test_construct_build_helper_with_wrong_project_file_path(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}))
        with self.assertRaises(ConanException):
            qbs.Qbs(conanfile, project_file='random/file/path')

    def test_add_configuration(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}))
        conanfile.folders.set_base_source('.')
        build_helper = qbs.Qbs(conanfile)
        configurations = {
            'debug':  {'products.MyLib.specialFlags': ['-frtti',
                                                       '-fexceptions']},
            'release': {'products.MyLib.specialFlags': ['-fno-exceptions',
                                                        '-fno-rtti']}
        }
        for name, config in configurations.items():
            build_helper.add_configuration(name, config)
        self.assertEqual(build_helper._configuration, configurations)

    def test_build(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}),
            runner=RunnerMock())
        conanfile.folders.set_base_source('.')
        conanfile.folders.set_base_build('.')
        build_helper = qbs.Qbs(conanfile)

        build_helper.build()
        self.assertEqual(
            conanfile.runner.command_called,
            ('qbs build --no-install --build-directory %s '
             '--file %s --jobs %s profile:%s') % (
                conanfile.build_folder, build_helper._project_file,
                build_helper.jobs, build_helper.profile))

        build_helper.build(products=['app1', 'app2', 'lib'])
        self.assertEqual(
            conanfile.runner.command_called,
            ('qbs build --no-install --build-directory %s '
             '--file %s --products app1,app2,lib --jobs %s profile:%s') % (
                conanfile.build_folder, build_helper._project_file,
                build_helper.jobs, build_helper.profile))

    def test_build_all(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}),
            runner=RunnerMock())
        conanfile.folders.set_base_source('.')
        conanfile.folders.set_base_build('.')
        build_helper = qbs.Qbs(conanfile)

        build_helper.build_all()
        self.assertEqual(
            conanfile.runner.command_called,
            ('qbs build --no-install --build-directory %s '
             '--file %s --all-products --jobs %s profile:%s') % (
                conanfile.build_folder, build_helper._project_file,
                build_helper.jobs, build_helper.profile))

    @unittest.skipIf(six.PY2, "Order of qbs output is defined only for PY3")
    def test_build_with_custom_configuration(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}),
            runner=RunnerMock())
        conanfile.folders.set_base_source('.')
        conanfile.folders.set_base_build('.')
        build_helper = qbs.Qbs(conanfile)
        config_name = 'debug'
        config_values = {
            'product.App.boolProperty': True,
            'product.App.intProperty': 1337,
            'product.App.stringProperty': 'Hello World',
            'product.App.stringListProperty': ['Hello', 'World']
        }
        build_helper.add_configuration(config_name, config_values)
        build_helper.build()
        self.assertEqual(
            conanfile.runner.command_called,
            ('qbs build --no-install --build-directory %s '
             '--file %s --jobs %s profile:%s '
             'config:%s %s:%s %s:%s %s:%s %s:%s') % (
                conanfile.build_folder, build_helper._project_file,
                build_helper.jobs, build_helper.profile,
                config_name,
                'product.App.boolProperty',
                'true',
                'product.App.intProperty',
                config_values['product.App.intProperty'],
                'product.App.stringProperty',
                config_values['product.App.stringProperty'],
                'product.App.stringListProperty',
                config_values['product.App.stringListProperty']))

    def test_install(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}),
            runner=RunnerMock())
        conanfile.folders.set_base_source('.')
        conanfile.folders.set_base_package("pkg")
        build_helper = qbs.Qbs(conanfile)

        build_helper.install()
        self.assertEqual(
            conanfile.runner.command_called,
            ('qbs install --no-build --install-root %s '
             '--file %s') % (
                conanfile.package_folder, build_helper._project_file))

    def test_install_with_custom_configuration(self):
        conanfile = MockConanfile(
            MockSettings({'os': 'Linux', 'compiler': 'gcc'}),
            runner=RunnerMock())
        conanfile.folders.set_base_source('.')
        conanfile.folders.set_base_package("pkg")
        build_helper = qbs.Qbs(conanfile)
        config_name = 'debug'
        config_values = {
            'product.App.boolProperty': True,
            'product.App.intProperty': 1337,
            'product.App.stringProperty': 'Hello World',
            'product.App.stringListProperty': ['Hello', 'World']
        }
        build_helper.add_configuration(config_name, config_values)

        build_helper.install()
        self.assertEqual(
            conanfile.runner.command_called,
            ('qbs install --no-build --install-root %s '
             '--file %s config:%s') % (
                conanfile.package_folder, build_helper._project_file,
                config_name))
