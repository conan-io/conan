import os

from conans import tools
from conans.errors import ConanException


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
        # hardcoded name, see qbs toolchain
        self.profile = 'conan_toolchain_profile'
        self._conanfile = conanfile
        self._set_project_file(project_file)
        self.jobs = tools.cpu_count()
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

    def build(self, products=None):
        products = products or []
        args = [
            '--no-install',
            '--build-directory', self._conanfile.build_folder,
            '--file', self._project_file,
        ]

        if products:
            args.extend(['--products', ','.join(products)])

        args.extend(['--jobs', '%s' % self.jobs])

        if self.profile:
            args.append('profile:%s' % self.profile)

        for name in self._configuration:
            config = self._configuration[name]
            args.extend(_configuration_dict_to_commandlist(name, config))

        cmd = 'qbs build %s' % (' '.join(args))
        self._conanfile.run(cmd)

    def build_all(self):
        args = [
            '--no-install',
            '--build-directory', self._conanfile.build_folder,
            '--file', self._project_file,
            '--all-products'
        ]

        args.extend(['--jobs', '%s' % self.jobs])

        if self.profile:
            args.append('profile:%s' % self.profile)

        for name in self._configuration:
            config = self._configuration[name]
            args.extend(_configuration_dict_to_commandlist(name, config))

        cmd = 'qbs build %s' % (' '.join(args))
        self._conanfile.run(cmd)

    def install(self):
        args = [
            '--no-build',
            '--install-root', self._conanfile.package_folder,
            '--file', self._project_file
        ]

        for name in self._configuration:
            args.append('config:%s' % name)

        cmd = 'qbs install %s' % (' '.join(args))
        self._conanfile.run(cmd)
