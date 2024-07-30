import os

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
    """
    Qbs helper to use together with the QbsDeps feature.
    This class provides helper methods that wraps calls to the Qbs tool.
    """
    def __init__(self, conanfile, project_file=None):
        """
        :param conanfile: The current recipe object. Always use ``self``.
        :param project_file: The name to the main project file. If not set, Qbs will try to
        autodetect the project file.
        """
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
        """
        Adds a build configuration for the multi-configuration build.
        This Qbs feature is rarely needed since each conan package can contain only one
        configuration, however might be useful when creating multiple versions of the same product
        that should be put in the same Conan package.
        :param name: the name of the configuration. This corresponds to the ``config`` parameter
        of ``qbs resolve``, ``qbs build`` and ``qbs install`` commands.
        :param values: the dict containing Qbs properties and their values for this configuration.
        """
        self._configuration[name] = values

    def _get_common_arguments(self):
        return [
            '--build-directory', self._conanfile.build_folder,
            '--file', self._project_file,
        ]

    def resolve(self, parallel=True):
        """
        Wraps the ``qbs revolve`` call.
        If QbsDeps generator is used, this will also set the necessary properites of the Qbs
        "conan" module provider automatically adding dependencies to the project.
        :param parallel: Whether to use multi-threaded resolving. Defaults to ``True``.
        """
        args = self._get_common_arguments()

        if parallel:
            args.extend(['--jobs', '%s' % self.jobs])
        else:
            args.extend(['--jobs', '1'])

        if self.profile:
            args.append('profile:%s' % self.profile)

        generators_folder = self._conanfile.generators_folder
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
        """
        Wraps the ``qbs build`` call.
        :param products: The list of product names to build. If not set, builds all products that
        have builtByDefault set to true. This parameter corresponds to the ``--products`` option
        of the ``qbs build`` command.
        The resolve() method should be called before calling this method.
        """
        return self._build(products=products, all_products=False)

    def build_all(self):
        """
        Wraps the ``qbs build --all-products`` call.
        This method builds all products, even if their builtByDefault property is false.
        The resolve() method should be called before calling this method.
        """
        return self._build(products=None, all_products=True)

    def install(self):
        """
        Wraps the ``qbs install`` call.
        Perfoms the installation of files marked as installable in the Qbs project.
        The build() or build_all() methods should be called before calling this method.
        """
        args = self._get_common_arguments()
        args.extend(['--no-build', '--install-root', self._conanfile.package_folder])

        for name in self._configuration:
            args.append('config:%s' % name)

        cmd = 'qbs install %s' % cmd_args_to_string(args)
        self._conanfile.run(cmd)
