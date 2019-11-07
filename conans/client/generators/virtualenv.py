import os

from conans.client.tools.oss import OSInfo
from conans.model import Generator


class VirtualEnvGenerator(Generator):

    append_with_spaces = ["CPPFLAGS", "CFLAGS", "CXXFLAGS", "LIBS", "LDFLAGS", "CL", "_LINK_"]
    suffix = ""
    venv_name = "conanenv"

    def __init__(self, conanfile):
        super(VirtualEnvGenerator, self).__init__(conanfile)
        self.conanfile = conanfile
        self.env = conanfile.env

    @property
    def filename(self):
        return

    @staticmethod
    def _variable_placeholder(flavor, name, append_with_spaces):
        """
        :param flavor: flavor of the execution environment
        :param name: variable name
        :return: placeholder for the variable name formatted for a certain execution environment.
        (e.g., cmd, ps1, sh).
        """
        if flavor == "cmd":
            return "%%%s%%" % name
        if flavor == "ps1":
            return "$env:%s" % name
        # flavor == sh
        return "${%s+ $%s}" % (name, name) if append_with_spaces else "${%s+:$%s}" % (name,  name)

    @classmethod
    def _format_values(cls, flavor, variables):
        """
        Formats the values for the different supported script language flavors.
        :param flavor: flavor of the execution environment
        :param variables: variables to be formatted
        :return:
        """
        if flavor == "cmd":
            path_sep, quote_elements, quote_full_value = ";", False, False
        elif flavor == "ps1":
            path_sep, quote_elements, quote_full_value = ";", False, True
        elif flavor == "sh":
            path_sep, quote_elements, quote_full_value = ":", True, False

        for name, value in variables:
            # activate values
            if isinstance(value, list):
                append_with_spaces = name in cls.append_with_spaces
                placeholder = cls._variable_placeholder(flavor, name, append_with_spaces)
                if append_with_spaces:
                    # Variables joined with spaces look like: CPPFLAGS="one two three"
                    value = " ".join(value+[placeholder])
                    value = "\"%s\"" % value if quote_elements else value
                else:
                    # Quoted variables joined with pathset may look like:
                    # PATH="one path":"two paths"
                    # Unquoted variables joined with pathset may look like: PATH=one path;two paths
                    value = ["\"%s\"" % v for v in value] if quote_elements else value
                    if flavor == "sh":
                        value = path_sep.join(value) + placeholder
                    else:
                        value = path_sep.join(value + [placeholder])
            else:
                # single value
                value = "\"%s\"" % value if quote_elements else value
            activate_value = "\"%s\"" % value if quote_full_value else value

            # deactivate values
            value = os.environ.get(name, "")
            deactivate_value = "\"%s\"" % value if quote_full_value or quote_elements else value
            yield name, activate_value, deactivate_value

    def _sh_lines(self):
        variables = [("OLD_PS1", "$PS1"),
                     ("PS1", "(%s) $PS1" % self.venv_name)]
        variables.extend(self.env.items())

        activate_lines = []
        deactivate_lines = ["%s=%s" % ("PS1", "$OLD_PS1"), "export PS1"]

        for name, activate, deactivate in self._format_values("sh", variables):
            activate_lines.append("%s=%s" % (name, activate))
            activate_lines.append("export %s" % name)
            if name != "PS1":
                if deactivate == '""':
                    deactivate_lines.append("unset %s" % name)
                else:
                    deactivate_lines.append("%s=%s" % (name, deactivate))
                    deactivate_lines.append("export %s" % name)
        activate_lines.append('')
        deactivate_lines.append('')
        return activate_lines, deactivate_lines

    def _cmd_lines(self):
        variables = [("PROMPT", "(%s) %%PROMPT%%" % self.venv_name)]
        variables.extend(self.env.items())

        activate_lines = ["@echo off"]
        deactivate_lines = ["@echo off"]
        for name, activate, deactivate in self._format_values("cmd", variables):
            activate_lines.append("SET %s=%s" % (name, activate))
            deactivate_lines.append("SET %s=%s" % (name, deactivate))
        activate_lines.append('')
        deactivate_lines.append('')
        return activate_lines, deactivate_lines

    def _ps1_lines(self):
        activate_lines = ['function global:_old_conan_prompt {""}',
                          '$function:_old_conan_prompt = $function:prompt',
                          'function global:prompt { write-host "(%s) " -nonewline;'
                          ' & $function:_old_conan_prompt }' % self.venv_name]
        deactivate_lines = ['$function:prompt = $function:_old_conan_prompt',
                            'remove-item function:_old_conan_prompt']
        for name, activate, deactivate in self._format_values("ps1", self.env.items()):
            activate_lines.append('$env:%s = %s' % (name, activate))
            deactivate_lines.append('$env:%s = %s' % (name, deactivate))
        activate_lines.append('')
        return activate_lines, deactivate_lines

    @property
    def content(self):
        os_info = OSInfo()
        result = {}
        if os_info.is_windows and not os_info.is_posix:
            activate, deactivate = self._cmd_lines()
            result["activate{}.bat".format(self.suffix)] = os.linesep.join(activate)
            result["deactivate{}.bat".format(self.suffix)] = os.linesep.join(deactivate)

            activate, deactivate = self._ps1_lines()
            result["activate{}.ps1".format(self.suffix)] = os.linesep.join(activate)
            result["deactivate{}.ps1".format(self.suffix)] = os.linesep.join(deactivate)

        activate, deactivate = self._sh_lines()
        result["activate{}.sh".format(self.suffix)] = os.linesep.join(activate)
        result["deactivate{}.sh".format(self.suffix)] = os.linesep.join(deactivate)

        return result
