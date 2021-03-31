import os
import platform
import textwrap
from collections import OrderedDict

from jinja2 import Template

from conans.errors import ConanException
from conans.util.files import normalize

sh_activate = textwrap.dedent("""\
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
""")

sh_deactivate = textwrap.dedent("""\
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
""")

bat_activate = textwrap.dedent("""\
    @echo off

    {%- for it in modified_vars %}
    SET "CONAN_OLD_{{it}}=%{{it}}%"
    {%- endfor %}

    FOR /F "usebackq tokens=1,* delims==" %%i IN ("{{ environment_file }}") DO (
        CALL SET "%%i=%%j"
    )

    SET "CONAN_OLD_PROMPT=%PROMPT%"
    SET "PROMPT=({{venv_name}}) %PROMPT%"
""")

bat_deactivate = textwrap.dedent("""\
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
""")

ps1_activate = textwrap.dedent("""\
    {%- for it in modified_vars %}
    $env:CONAN_OLD_{{venv_name}}_{{it}}=$env:{{it}}
    {%- endfor %}

    foreach ($line in Get-Content "{{ environment_file }}") {
        $var,$value = $line -split '=',2
        $value_expanded = $ExecutionContext.InvokeCommand.ExpandString($value)
        Set-Item env:\\$var -Value "$value_expanded"
    }

    function global:_old_conan_{{venv_name}}_prompt {""}
    $function:_old_conan_{{venv_name}}_prompt = $function:prompt
    function global:prompt {
        write-host "({{venv_name}}) " -nonewline; & $function:_old_conan_{{venv_name}}_prompt
    }
""")

ps1_deactivate = textwrap.dedent("""\
    $function:prompt = $function:_old_conan_{{venv_name}}_prompt
    remove-item function:_old_conan_{{venv_name}}_prompt

    {% for it in modified_vars %}
    $env:{{it}}=$env:CONAN_OLD_{{venv_name}}_{{it}}
    Remove-Item env:CONAN_OLD_{{venv_name}}_{{it}}
    {%- endfor %}
    {%- for it in new_vars %}
    Remove-Item env:{{it}}
    {%- endfor %}
""")


BAT_FLAVOR = "bat"
PS1_FLAVOR = "ps1"
SH_FLAVOR = "sh"


def _variable_placeholder(flavor, name, append_with_spaces):
    """
    :param flavor: flavor of the execution environment
    :param name: variable name
    :return: placeholder for the variable name formatted for a certain execution environment.
    (e.g., cmd, ps1, sh).
    """
    if flavor == BAT_FLAVOR:
        return "%{}%".format(name)
    if flavor == PS1_FLAVOR:
        return "$env:%s" % name
    # flavor == sh
    return "${%s:+ $%s}" % (name, name) if append_with_spaces else "${%s:+:$%s}" % (name,  name)


def _format_values(flavor, variables, append_with_spaces):
    """
    Formats the values for the different supported script language flavors.
    :param flavor: flavor of the execution environment
    :param variables: variables to be formatted
    :return:
    """

    if flavor in [BAT_FLAVOR, PS1_FLAVOR] and platform.system() == "Windows":
        path_sep, quote_elements = ";", False
    elif flavor == PS1_FLAVOR:
        path_sep, quote_elements = ":", False
    else:
        path_sep, quote_elements = ":", True

    for name, value in variables:
        # activate values
        if isinstance(value, list):
            value = list(OrderedDict.fromkeys(value))  # Avoid repeated entries, while keeping order
            append_space = name in append_with_spaces
            placeholder = _variable_placeholder(flavor, name, append_space)
            if append_space:
                # Variables joined with spaces look like: CPPFLAGS="one two three"
                if flavor == SH_FLAVOR:
                    value = " ".join(value) + placeholder
                else:
                    value = " ".join(value + [placeholder])
                value = "\"%s\"" % value if quote_elements else value
            else:
                # Quoted variables joined with pathset may look like:
                # PATH="one path":"two paths"
                # Unquoted variables joined with pathset may look like: PATH=one path;two paths
                value = ["\"%s\"" % v for v in value] if quote_elements else value
                if flavor == SH_FLAVOR:
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


def _files(env_vars, vars_with_spaces, flavor, activate_tpl, deactivate_tpl, venv_name,
           env_filepath):
    ret = list(_format_values(flavor, env_vars.items(), vars_with_spaces))
    modified_vars = [name for name, _, existing in ret if existing]
    new_vars = [name for name, _, existing in ret if not existing]

    activate_content = activate_tpl.render(environment_file=env_filepath,
                                           modified_vars=modified_vars, new_vars=new_vars,
                                           venv_name=venv_name)
    deactivate_content = deactivate_tpl.render(modified_vars=modified_vars, new_vars=new_vars,
                                               venv_name=venv_name)

    environment_lines = ["{}={}".format(name, value) for name, value, _ in ret]
    # This blank line is important, otherwise the script doens't process last line
    environment_lines.append('')

    if flavor == SH_FLAVOR:
        # replace CRLF->LF guarantee it is always LF, irrespective of current .py file
        activate_content = activate_content.replace("\r\n", "\n")
        deactivate_content = deactivate_content.replace("\r\n", "\n")
        environment = "\n".join(environment_lines)
    else:
        activate_content = normalize(activate_content)
        deactivate_content = normalize(deactivate_content)
        environment = os.linesep.join(environment_lines)

    return activate_content, deactivate_content, environment


def env_files(env_vars, vars_with_spaces, flavor, folder, name, venv_name):
    env_filename = "environment{}.{}.env".format(name, flavor)
    activate_filename = "activate{}.{}".format(name, flavor)
    deactivate_filename = "deactivate{}.{}".format(name, flavor)

    templates = {SH_FLAVOR: (sh_activate, sh_deactivate),
                 BAT_FLAVOR: (bat_activate, bat_deactivate),
                 PS1_FLAVOR: (ps1_activate, ps1_deactivate)}
    try:
        activate, deactivate = templates[flavor]
    except KeyError:
        raise ConanException("Unrecognized flavor: %s" % flavor)
    activate_tpl, deactivate_tpl = Template(activate), Template(deactivate)

    env_filepath = os.path.abspath(os.path.join(folder, env_filename))
    activate, deactivate, envfile = _files(env_vars, vars_with_spaces, flavor, activate_tpl,
                                           deactivate_tpl, venv_name, env_filepath)

    result = {activate_filename: activate,
              deactivate_filename: deactivate,
              env_filename: envfile}
    return result
