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
    
    FOR /F "usebackq tokens=1,* delims==" %%i IN ("{{ environment_file }}") DO (
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
        if flavor in ["cmd", "ps1"]:
            path_sep, quote_elements = ";", False
        elif flavor == "sh":
            path_sep, quote_elements = ":", True

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
            if platform.system() != "Windows":
                value = value.replace("\\", "\\\\")

            # deactivate values
            existing = name in os.environ
            yield name, value, existing

    def _files(self, flavor, activate_tpl, deactivate_tpl, environment_filename):
        ret = list(self._format_values(flavor, self.env.items()))
        modified_vars = [name for name, _, existing in ret if existing]
        new_vars = [name for name, _, existing in ret if not existing]

        environment_filepath = os.path.abspath(os.path.join(self.output_path, environment_filename))
        activate_content = activate_tpl.render(environment_file=environment_filepath,
                                               modified_vars=modified_vars, new_vars=new_vars,
                                               venv_name=self.venv_name)
        deactivate_content = deactivate_tpl.render(modified_vars=modified_vars, new_vars=new_vars)

        environment_lines = ["{}={}".format(name, value) for name, value, _ in ret]
        environment_lines.append('')

        return activate_content, deactivate_content, os.linesep.join(environment_lines)

    @property
    def content(self):
        result = {}

        def _call_files(flavor, activate_tpl, deactivate_tpl, file_ext=None):
            file_ext = file_ext or flavor
            environment_filename = "environment{}.{}.env".format(self.suffix, file_ext)
            activate, deactivate, envfile = self._files(flavor, activate_tpl, deactivate_tpl,
                                                        environment_filename)

            result["activate{}.{}".format(self.suffix, file_ext)] = activate
            result["deactivate{}.{}".format(self.suffix, file_ext)] = deactivate
            result[environment_filename] = envfile

        os_info = OSInfo()
        if os_info.is_windows and not os_info.is_posix:
            _call_files('cmd', cmd_activate_tpl, cmd_deactivate_tpl, 'bat')
            _call_files('ps1', ps1_activate_tpl, ps1_deactivate_tpl)
        _call_files("sh", sh_activate_tpl, sh_deactivate_tpl)

        return result
