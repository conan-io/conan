import os

from conans import tools
from conans.errors import ConanException


class QbsException(ConanException):
    def __str__(self):
        msg = super(QbsException, self).__str__()
        return "Qbs build helper: {}".format(msg)


def _configuration_dict_to_commandlist(name, dict):
    command_list = ["config:%s" % name]
    for key, value in dict.items():
        if type(value) is bool:
            if value:
                b = "true"
            else:
                b = "false"
            command_list.append("%s:%s" % (key, b))
        else:
            command_list.append("%s:%s" % (key, value))
    return command_list


class Qbs(object):
    def __init__(self, conanfile, project_file=None):
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
            raise QbsException("could not find project file")

    def add_configuration(self, name, values):
        self._configuration[name] = values

    def build(self, products=[]):
        args = [
            "--no-install",
            "--build-directory", self._conanfile.build_folder,
            "--file", self._project_file,
        ]

        if products:
            args.extend(["--products", ",".join(products)])

        args.extend(["--jobs", "%s" % self.jobs])

        for name in self._configuration:
            config = self._configuration[name]
            args.extend(_configuration_dict_to_commandlist(name, config))

        cmd = "qbs build %s" % (" ".join(args))
        self._conanfile.run(cmd)

    def build_all(self):
        args = [
            "--no-install",
            "--build-directory", self._conanfile.build_folder,
            "--file", self._project_file,
            "--all-products"
        ]

        args.extend(["--jobs", "%s" % self.jobs])

        for name in self._configuration:
            config = self._configuration[name]
            args.extend(_configuration_dict_to_commandlist(name, config))

        cmd = "qbs build %s" % (" ".join(args))
        self._conanfile.run(cmd)

    def install(self):
        args = [
            "--no-build",
            "--clean-install-root",
            "--install-root", self._conanfile.install_folder,
            "--file", self._project_file
        ]

        for name in self._configuration:
            args.append("config:%s" % (name))

        cmd = "qbs install %s" % (" ".join(args))
        self._conanfile.run(cmd)
