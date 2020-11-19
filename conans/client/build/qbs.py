import os
import platform

from conans import tools
from conans.errors import ConanException


class QbsException(ConanException):
    def __str__(self):
        msg = super(QbsException, self).__str__()
        return "Qbs build helper: {}".format(msg)


def _qbs_config(conanfile, profile_name, values):
    key_prefix = "profiles.%s" % profile_name
    for key, value in values.items():
        config_key = "%s.%s" % (key_prefix, key)
        if type(value) is bool:
            if value:
                value = 'true'
            else:
                value = 'false'
        cmd = 'qbs-config --settings-dir %s %s "%s"' % (
              _settings_dir(conanfile), config_key, value)
        conanfile.run(cmd)


def _env_var_to_list(var):
    elements = []
    flag_groups = var.split('"')

    latest_flag = ''
    for i in range(len(flag_groups)):
        if not flag_groups[i]:
            continue

        def is_quoted_flag():
            return i % 2

        if is_quoted_flag():
            if latest_flag:
                elements.append(latest_flag + flag_groups[i])
            else:
                elements.append(flag_groups[i])
        else:
            flags = flag_groups[i].split()
            latest_flag = flags.pop()
            for s in flags:
                elements.append(s)
            if not latest_flag.endswith('='):
                elements.append(latest_flag)
                latest_flag = ''

    return elements


def _check_for_compiler(conanfile):
    compiler = conanfile.settings.get_safe("compiler")
    if not compiler:
        raise QbsException("need compiler to be set in settings")

    if compiler not in ["Visual Studio", "gcc", "clang"]:
        raise QbsException("compiler not supported")


def _compiler_name(conanfile):
    # needs more work since currently only windows and linux is supported
    compiler = conanfile.settings.compiler
    if platform.system() == "Windows":
        if compiler == "gcc":
            return "mingw"
        if compiler == "Visual Studio":
            if tools.msvs_toolset(conanfile) == "ClangCl":
                return "clang-cl"
            return "cl"
        if compiler == "clang":
            return "clang-cl"
        raise QbsException("unknown windows compiler")

    if platform.system() == "Linux":
        return compiler

    raise QbsException("unknown compiler")


def _generate_profile_name(conanfile):
    compiler = "_%s" % (conanfile.settings.get_safe("compiler"))
    compiler_version = conanfile.settings.compiler.get_safe(
        "version")
    if compiler_version:
        compiler_version = '_' + compiler_version
    the_os = conanfile.settings.get_safe("os")
    if the_os:
        the_os = '_' + the_os

    return "_conan%s%s%s" % (the_os, compiler, compiler_version)


def _settings_dir(conanfile):
    return conanfile.build_folder


def _setup_toolchain(conanfile, profile_name):
    if tools.get_env("CC"):
        compiler = tools.get_env("CC")
    else:
        compiler = _compiler_name(conanfile)

    env_context = tools.no_op()
    if platform.system() == "Windows":
        if compiler in ["cl", "clang-cl"]:
            env_context = tools.vcvars()

    with env_context:
        cmd = "qbs-setup-toolchains --settings-dir %s %s %s" % (
              _settings_dir(conanfile), compiler, profile_name)
        conanfile.run(cmd)

    flags_from_env = {}
    if tools.get_env("ASFLAGS"):
        flags_from_env["cpp.assemblerFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("ASFLAGS")))
    if tools.get_env("CFLAGS"):
        flags_from_env["cpp.cFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("CFLAGS")))
    if tools.get_env("CPPFLAGS"):
        flags_from_env["cpp.cppFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("CPPFLAGS")))
    if tools.get_env("CXXFLAGS"):
        flags_from_env["cpp.cxxFlags"] = '%s' % (
            _env_var_to_list(tools.get_env("CXXFLAGS")))
    if tools.get_env("LDFLAGS"):
        ld_flags = []
        for item in _env_var_to_list(tools.get_env("LDFLAGS")):
            flags = item[len("-Wl,"):]
            ld_flags.extend(flags.split(","))
        flags_from_env["cpp.linkerFlags"] = '%s' % (ld_flags)

    if flags_from_env:
        _qbs_config(conanfile, profile_name, flags_from_env)


def _configuration_dict_to_commandlist(name, dict):
    command_list = ["config:%s" % name]
    for key in dict:
        value = dict[key]
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
        _check_for_compiler(conanfile)
        self._conanfile = conanfile
        self._set_project_file(project_file)
        self._base_profile_name = _generate_profile_name(conanfile)
        _setup_toolchain(conanfile, self._base_profile_name)
        self.jobs = tools.cpu_count()
        self._configuration = dict()
        self._profile_name = ""

    def _set_project_file(self, project_file):
        if not project_file:
            self._project_file = self._conanfile.source_folder
        else:
            self._project_file = project_file

        if not os.path.exists(self._project_file):
            raise QbsException("could not find project file")

    def setup_profile(self, name, values):
        temp = {"baseProfile": self._base_profile_name}
        temp.update(values)
        _qbs_config(self._conanfile, name, temp)
        self._profile_name = name

    def add_configuration(self, name, values):
        self._configuration[name] = values

    def build(self, all_products=False, products=[]):
        if not self._profile_name:
            self._profile_name = self._base_profile_name

        args = [
            "--no-install",
            "--settings-dir", _settings_dir(self._conanfile),
            "--build-directory", self._conanfile.build_folder,
            "--file", self._project_file,
        ]

        if all_products:
            args.append("--all-products")
        if products:
            args.extend(["-p", ",".join(products)])

        args.extend(["--jobs", "%s" % self.jobs])
        args.append("profile:%s" % self._profile_name)

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
