import copy
import os
import platform

from conans.model import Generator


def get_setenv_variables_commands(multiple_to_set, simple_to_set, command_set=None):
    if command_set is None:
        command_set = "SET" if platform.system() == "Windows" else "export"

    ret = []
    for name, values in multiple_to_set.items():
        if platform.system() == "Windows":
            value = os.pathsep.join(values)
            ret.append(command_set + ' "' + name + '=' + value + ';%' + name + '%"')
        else:
            value = os.pathsep.join(['"%s"' % val for val in values])
            # Standard UNIX "sh" does not allow "export VAR=xxx" on one line
            # So for portability reasons we split into two commands
            ret.append(name + '=' + value + ':$' + name)
            ret.append(command_set + ' ' + name)
    for name, value in simple_to_set.items():
        if platform.system() == "Windows":
            ret.append(command_set + ' "' + name + '=' + value + '"')
        else:
            ret.append(name + '=' + value)
            ret.append(command_set + ' ' + name + '=' + value)
    return ret


class VirtualEnvGenerator(Generator):

    def __init__(self, conanfile):
        self.simple_env_vars, self.multiple_env_vars = conanfile.env_values_dicts
        super(VirtualEnvGenerator, self).__init__(conanfile)

    @property
    def filename(self):
        return

    def _activate_lines(self, venv_name):
        activate_lines = ["@echo off"] if platform.system() == "Windows" else []
        if platform.system() == "Windows":
            activate_lines.append("SET PROMPT=(%s) " % venv_name + "%PROMPT%")
        else:
            activate_lines.append("export OLD_PS1=\"$PS1\"")
            activate_lines.append("export PS1=\"(%s) " % venv_name + "$PS1\"")

        activate_commands = get_setenv_variables_commands(self.multiple_env_vars, self.simple_env_vars)
        activate_lines.extend(activate_commands)
        return activate_lines

    def _deactivate_lines(self):
        deactivate_lines = ["@echo off"] if platform.system() == "Windows" else []

        def append_deactivate_lines(var_names):
            ret = []
            for name in var_names:
                old_value = os.environ.get(name, "")
                if platform.system() == "Windows":
                    ret.append('SET "%s=%s"' % (name, old_value))
                else:
                    ret.append('export %s=%s' % (name, old_value))

            if platform.system() == "Windows":
                ret.append("SET PROMPT=%s" % os.environ.get("PROMPT", ""))
            else:
                ret.append('export PS1="$OLD_PS1"')
            return ret

        deactivate_lines.extend(append_deactivate_lines(self.simple_env_vars.keys()))
        deactivate_lines.extend(append_deactivate_lines(self.multiple_env_vars.keys()))
        return deactivate_lines

    def _ps1_lines(self, venv_name):
        deactivate_lines = []
        activate_lines = []
        all_vars = copy.copy(self.multiple_env_vars)
        all_vars.update(self.simple_env_vars)
        activate_lines.append("function global:_old_conan_prompt {\"\"}")
        activate_lines.append("$function:_old_conan_prompt = $function:prompt")
        activate_lines.append(
            "function global:prompt { write-host \"(%s) \" -nonewline; & $function:_old_conan_prompt }" % venv_name)
        deactivate_lines.append("$function:prompt = $function:_old_conan_prompt")
        deactivate_lines.append("remove-item function:\\_old_conan_prompt")
        for var_name in all_vars.keys():
            old_value = os.environ.get(var_name, "")
            deactivate_lines.append("$env:%s = \"%s\"" % (var_name, old_value))
        for name, value in self.multiple_env_vars.items():
            value = os.pathsep.join(value)
            activate_lines.append("$env:%s = \"%s\" + \";$env:%s\"" % (name, value, name))
        for name, value in self.simple_env_vars.items():
            activate_lines.append("$env:%s = \"%s\"" % (name, value))
        return activate_lines, deactivate_lines

    @property
    def content(self):

        venv_name = os.path.basename(self.conanfile.conanfile_directory)

        deactivate_lines = self._deactivate_lines()
        activate_lines = self._activate_lines(venv_name)

        ext = "bat" if platform.system() == "Windows" else "sh"
        result = {"activate.%s" % ext: os.linesep.join(activate_lines),
                  "deactivate.%s" % ext: os.linesep.join(deactivate_lines)}

        if platform.system() == "Windows":
            ps1_activate, ps1_deactivate = self._ps1_lines(venv_name)
            alt_shell = {"activate.ps1": os.linesep.join(ps1_activate),
                         "deactivate.ps1": os.linesep.join(ps1_deactivate)}
            result.update(alt_shell)
        return result
