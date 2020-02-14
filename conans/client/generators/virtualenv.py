import os
import platform
import textwrap

from jinja2 import Template

from conans.client.tools.oss import OSInfo
from conans.model import Generator


sh_activate_tpl = Template(textwrap.dedent("""\
    #!/usr/bin/env sh

    {%- for it in modified_vars %}
    export CONAN_OLD_{{it}}="${{it}}"
    {%- endfor %}

    while read -r line; do
        LINE="$(eval echo $line)";
        export "$LINE";
    done < "{{ environment_file }}"

    export CONAN_OLD_PS1="$PS1"
    export PS1="({{venv_name}}) $PS1"

"""))

sh_deactivate_tpl = Template(textwrap.dedent("""\
    #!/usr/bin/env sh
    export PS1="$CONAN_OLD_PS1"
    unset CONAN_OLD_PS1

    {% for it in modified_vars %}
    export {{it}}="$CONAN_OLD_{{it}}"
    unset CONAN_OLD_{{it}}
    {%- endfor %}
    {%- for it in new_vars %}
    unset {{it}}
    {%- endfor %}
"""))

cmd_activate_tpl = Template(textwrap.dedent("""\
    @echo off
    
    {%- for it in modified_vars %}
    SET "CONAN_OLD_{{it}}=%{{it}}%"
    {%- endfor %}
    
    FOR /F "usebackq tokens=1,* delims={{delim}}" %%i IN ("{{ environment_file }}") DO (
        CALL SET "%%i=%%j"
    )
    
    SET "CONAN_OLD_PROMPT=%PROMPT%"
    SET "PROMPT=({{venv_name}}) %PROMPT%"
"""))

cmd_deactivate_tpl = Template(textwrap.dedent("""\
    @echo off
    
    SET "PROMPT=%CONAN_OLD_PROMPT%"
    SET "CONAN_OLD_PROMPT="
    
    {% for it in modified_vars %}
    SET "{{it}}=%CONAN_OLD_{{it}}%"
    SET "CONAN_OLD_{{it}}="
    {%- endfor %}
    {%- for it in new_vars %}
    SET "{{it}}="
    {%- endfor %}
"""))

ps1_activate_tpl = Template(textwrap.dedent("""\
    {%- for it in modified_vars %}
    $env:CONAN_OLD_{{it}}=$env:{{it}}
    {%- endfor %}
    
    foreach ($line in Get-Content "{{ environment_file }}") {
        $var,$value = $line -split '=',2
        $value_expanded = $ExecutionContext.InvokeCommand.ExpandString($value)
        Set-Item env:\\$var -Value "$value_expanded"
    }
    
    function global:_old_conan_prompt {""}
    $function:_old_conan_prompt = $function:prompt
    function global:prompt { write-host "({{venv_name}}) " -nonewline; & $function:_old_conan_prompt }
"""))

ps1_deactivate_tpl = Template(textwrap.dedent("""\
    $function:prompt = $function:_old_conan_prompt
    remove-item function:_old_conan_prompt
    
    {% for it in modified_vars %}
    $env:{{it}}=$env:CONAN_OLD_{{it}}
    Remove-Item env:CONAN_OLD_{{it}}
    {%- endfor %}
    {%- for it in new_vars %}
    Remove-Item env:{{it}}
    {%- endfor %}
"""))


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
            return "%{}%".format(name)
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
            path_sep, quote_elements, quote_full_value = ";", False, False
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
            if platform.system() != "Windows":
                activate_value = activate_value.replace("\\", "\\\\")

            # deactivate values
            existing = name in os.environ
            #value = os.environ.get(name, "")
            #deactivate_value = "\"%s\"" % value if quote_full_value or quote_elements else value
            yield name, activate_value, existing

    def _sh_lines(self):
        ret = list(self._format_values("sh", self.env.items()))
        modified_vars = [it[0] for it in ret if it[2]]
        new_vars = [it[0] for it in ret if not it[2]]

        environment_filepath = os.path.abspath(
            os.path.join(self.output_path, "environment{}.sh.env".format(self.suffix)))
        activate_content = sh_activate_tpl.render(environment_file=environment_filepath,
                                                  modified_vars=modified_vars, new_vars=new_vars,
                                                  venv_name=self.venv_name)
        activate_lines = activate_content.splitlines()
        deactivate_content = sh_deactivate_tpl.render(modified_vars=modified_vars, new_vars=new_vars)
        deactivate_lines = deactivate_content.splitlines()

        environment_lines = []
        for name, activate, _ in self._format_values("sh", self.env.items()):
            environment_lines.append("%s=%s" % (name, activate))

        environment_lines.append('')
        return activate_lines, deactivate_lines, environment_lines

    def _cmd_lines(self):
        ret = list(self._format_values("cmd", self.env.items()))
        modified_vars = [it[0] for it in ret if it[2]]
        new_vars = [it[0] for it in ret if not it[2]]

        environment_filepath = os.path.abspath(
            os.path.join(self.output_path, "environment{}.bat.env".format(self.suffix)))
        activate_content = cmd_activate_tpl.render(environment_file=environment_filepath,
                                                   modified_vars=modified_vars, new_vars=new_vars,
                                                   delim="=",  # TODO: Test a env var with '=' in the value, it will require quotes around it
                                                   venv_name=self.venv_name)
        activate_lines = activate_content.splitlines()
        deactivate_content = cmd_deactivate_tpl.render(modified_vars=modified_vars, new_vars=new_vars)
        deactivate_lines = deactivate_content.splitlines()

        environment_lines = []
        for name, activate, _ in ret:
            environment_lines.append("%s=%s" % (name, activate))  # TODO: May need extra quotes here
        environment_lines.append('')

        return activate_lines, deactivate_lines, environment_lines

    def _ps1_lines(self):
        ret = list(self._format_values("ps1", self.env.items()))
        modified_vars = [it[0] for it in ret if it[2]]
        new_vars = [it[0] for it in ret if not it[2]]

        environment_filepath = os.path.abspath(
            os.path.join(self.output_path, "environment{}.ps1.env".format(self.suffix)))
        activate_content = ps1_activate_tpl.render(environment_file=environment_filepath,
                                                   modified_vars=modified_vars, new_vars=new_vars,
                                                   venv_name=self.venv_name)
        activate_lines = activate_content.splitlines()
        deactivate_content = ps1_deactivate_tpl.render(modified_vars=modified_vars, new_vars=new_vars)
        deactivate_lines = deactivate_content.splitlines()

        environment_lines = []
        for name, activate, _ in ret:
            environment_lines.append("%s=%s" % (name, activate))
        environment_lines.append('')

        return activate_lines, deactivate_lines, environment_lines

    @property
    def content(self):
        os_info = OSInfo()
        result = {}
        if os_info.is_windows and not os_info.is_posix:
            activate, deactivate, envfile = self._cmd_lines()
            result["activate{}.bat".format(self.suffix)] = os.linesep.join(activate)
            result["deactivate{}.bat".format(self.suffix)] = os.linesep.join(deactivate)
            result["environment{}.bat.env".format(self.suffix)] = os.linesep.join(envfile)

            activate, deactivate, envfile = self._ps1_lines()
            result["activate{}.ps1".format(self.suffix)] = os.linesep.join(activate)
            result["deactivate{}.ps1".format(self.suffix)] = os.linesep.join(deactivate)
            result["environment{}.ps1.env".format(self.suffix)] = os.linesep.join(envfile)

        activate, deactivate, envfile = self._sh_lines()
        result["activate{}.sh".format(self.suffix)] = os.linesep.join(activate)
        result["deactivate{}.sh".format(self.suffix)] = os.linesep.join(deactivate)
        result["environment{}.sh.env".format(self.suffix)] = os.linesep.join(envfile)

        return result
