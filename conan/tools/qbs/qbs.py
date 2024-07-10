import os
import shutil

from conan.tools.build import build_jobs, cmd_args_to_string
from conan.errors import ConanException

def _configuration_dict_to_commandlist(name, config_dict):
    command_list = ['config:%s' % name]
    for key, value in config_dict.items():
        if type(value) is bool:
            if value:
                b = 'true'
            else:
                b = 'false'
            command_list.append('%s:%s' % (key, b))
        else:
            command_list.append('%s:%s' % (key, value))
    return command_list


class Qbs(object):
    def __init__(self, conanfile, project_file=None):
        self.profile = None
        self._conanfile = conanfile
        self._set_project_file(project_file)
        self.jobs = build_jobs(conanfile)
        self._configuration = dict()

    def _set_project_file(self, project_file):
        if not project_file:
            self._project_file = self._conanfile.source_folder
        else:
            self._project_file = project_file

        if not os.path.exists(self._project_file):
            raise ConanException('Qbs: could not find project file %s' % self._project_file)

    def add_configuration(self, name, values):
        self._configuration[name] = values

    def _qbs_settings_paths(self):
        generators_folder = self._conanfile.generators_folder
        qbs_settings_path = os.path.join(generators_folder, 'qbs_settings.txt')
        if not os.path.exists(qbs_settings_path):
            return None, None
        return os.path.join(generators_folder, 'conan-qbs-settings-dir'), qbs_settings_path

    def _get_common_arguments(self):
        args = []
        settings_dir, _ = self._qbs_settings_paths()
        if settings_dir is not None:
            args.extend(['--settings-dir', settings_dir])
        args.extend([
            '--build-directory', self._conanfile.build_folder,
            '--file', self._project_file,
        ])
        return args

    def resolve(self, parallel=True):
        generators_folder = self._conanfile.generators_folder
        settings_dir, settings_path = self._qbs_settings_paths()
        if settings_dir is not None:
            shutil.rmtree(settings_dir, ignore_errors=True)
            import_args = ['--settings-dir', settings_dir, '--import', settings_path]
            import_cmd = 'qbs config  %s' % cmd_args_to_string(import_args)
            self._conanfile.run(import_cmd)

        args = self._get_common_arguments()

        if parallel:
            args.extend(['--jobs', '%s' % self.jobs])
        else:
            args.extend(['--jobs', '1'])

        if self.profile:
            args.append('profile:%s' % self.profile)

        if os.path.exists(os.path.join(generators_folder, 'conan-qbs-deps')):
            args.append('moduleProviders.conan.installDirectory:' + generators_folder)

        for name in self._configuration:
            config = self._configuration[name]
            args.extend(_configuration_dict_to_commandlist(name, config))

        cmd = 'qbs resolve %s' % cmd_args_to_string(args)
        self._conanfile.run(cmd)

    def _build(self, products, all_products):

        args = self._get_common_arguments()
        args.append('--no-install')

        if all_products:
            args.append('--all-products')
        elif products:
            args.extend(['--products', ','.join(products or [])])

        args.extend(['--jobs', '%s' % self.jobs])

        for name in self._configuration:
            args.append('config:%s' % name)

        cmd = 'qbs build %s' % cmd_args_to_string(args)
        self._conanfile.run(cmd)

    def build(self, products=None):
        return self._build(products=products, all_products=False)

    def build_all(self):
        return self._build(products=None, all_products=True)

    def install(self):
        args = self._get_common_arguments()
        args.extend(['--no-build', '--install-root', self._conanfile.package_folder])

        for name in self._configuration:
            args.append('config:%s' % name)

        cmd = 'qbs install %s' % cmd_args_to_string(args)
        self._conanfile.run(cmd)
