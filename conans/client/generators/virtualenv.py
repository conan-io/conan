import os
import platform
from conans.model import Generator


class VirtualEnvGenerator(Generator):

    append_with_spaces = ["CPPFLAGS", "CFLAGS", "CXXFLAGS", "LIBS", "LDFLAGS", "CL"]

    def __init__(self, conanfile):
        self.conanfile = conanfile
        self.env = conanfile.env
        self.venv_name = "conanenv"
        super(VirtualEnvGenerator, self).__init__(conanfile)

    @property
    def filename(self):
        return

    def _get_setenv_variables_commands(self):
        command_set = "SET" if platform.system() == "Windows" else "export"
        ret = []
        for name, value in self.env.items():
            if platform.system() == "Windows":
                if isinstance(value, list):
                    value = os.pathsep.join(value)
                    ret.append(command_set + ' ' + name + '=' + value + ';%' + name + '%')
                else:
                    # CMake crashes with quotes in CXX and CC, it seems
                    # that windows doesn't need the quotes, it handles right
                    # the spaces: #1169
                    ret.append(command_set + ' ' + name + '=' + value)
            else:
                if isinstance(value, list):
                    if name in self.append_with_spaces:
                        # Variables joined with spaces look like: CPPFLAGS="one two three"
                        value = " ".join(value)
                        ret.append(name + '="' + value + '%s$' % " " + name + '"')
                    else:
                        # Variables joined with : or ; (os.pathset) look like: PATH="one path":"two paths"
                        value = os.pathsep.join(['"%s"' % val for val in value])
                        ret.append(name + '=' + value + '%s$' % os.pathsep + name)

                    # Standard UNIX "sh" does not allow "export VAR=xxx" on one line
                    # So for portability reasons we split into two commands
                    ret.append(command_set + ' ' + name)
                else:
                    ret.append(name + '="' + value + '"')
                    ret.append(command_set + ' ' + name)

        return ret

    def _activate_lines(self, venv_name):
        activate_lines = ["@echo off"] if platform.system() == "Windows" else []
        if platform.system() == "Windows":
            activate_lines.append("SET PROMPT=(%s) " % venv_name + "%PROMPT%")
        else:
            activate_lines.append("export OLD_PS1=\"$PS1\"")
            activate_lines.append("export PS1=\"(%s) " % venv_name + "$PS1\"")

        activate_commands = self._get_setenv_variables_commands()
        activate_lines.extend(activate_commands)
        return activate_lines

    def _deactivate_lines(self):
        deactivate_lines = ["@echo off"] if platform.system() == "Windows" else []

        def append_deactivate_lines(var_names):
            ret = []
            for name in var_names:
                old_value = os.environ.get(name, "")
                if platform.system() == "Windows":
                    ret.append('SET %s=%s' % (name, old_value))
                else:
                    ret.append('export %s=%s' % (name, old_value))

            if platform.system() == "Windows":
                ret.append("SET PROMPT=%s" % os.environ.get("PROMPT", ""))
            else:
                ret.append('export PS1="$OLD_PS1"')
            return ret
        deactivate_lines.extend(append_deactivate_lines(self.env.keys()))
        return deactivate_lines

    def _ps1_lines(self, venv_name):
        deactivate_lines = []
        activate_lines = ["function global:_old_conan_prompt {\"\"}"]
        activate_lines.append("$function:_old_conan_prompt = $function:prompt")
        activate_lines.append(
            "function global:prompt { write-host \"(%s) \" -nonewline; & $function:_old_conan_prompt }" % venv_name)
        deactivate_lines.append("$function:prompt = $function:_old_conan_prompt")
        deactivate_lines.append("remove-item function:\\_old_conan_prompt")
        for var_name in self.env.keys():
            old_value = os.environ.get(var_name, "")
            deactivate_lines.append("$env:%s = \"%s\"" % (var_name, old_value))
        for name, value in self.env.items():
            if isinstance(value, list):
                value = os.pathsep.join(value)
                activate_lines.append("$env:%s = \"%s\" + \";$env:%s\"" % (name, value, name))
            else:
                activate_lines.append("$env:%s = \"%s\"" % (name, value))

        return activate_lines, deactivate_lines

    @property
    def content(self):
        deactivate_lines = self._deactivate_lines()
        activate_lines = self._activate_lines(self.venv_name)

        ext = "bat" if platform.system() == "Windows" else "sh"
        result = {"activate.%s" % ext: os.linesep.join(activate_lines),
                  "deactivate.%s" % ext: os.linesep.join(deactivate_lines)}

        if platform.system() == "Windows":
            ps1_activate, ps1_deactivate = self._ps1_lines(self.venv_name)
            alt_shell = {"activate.ps1": os.linesep.join(ps1_activate),
                         "deactivate.ps1": os.linesep.join(ps1_deactivate)}
            result.update(alt_shell)
        return result
