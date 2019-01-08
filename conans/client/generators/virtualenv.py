import os
from abc import ABCMeta, abstractmethod, abstractproperty
from itertools import chain
from textwrap import dedent

from conans.client.tools.oss import OSInfo
from conans.model import Generator


class BasicScriptGenerator(object):
    __metaclass__ = ABCMeta

    append_with_spaces = [
        "CPPFLAGS", "CFLAGS", "CXXFLAGS", "LIBS", "LDFLAGS", "CL"
    ]

    def __init__(self, name, env):
        self.name = name
        self.env = env

    def activate_lines(self):
        yield self.activate_prefix

        for name, value in self.env.items():
            if isinstance(value, list):
                placeholder = self.placeholder_format.format(name)
                if name in self.append_with_spaces:
                    # Variables joined with spaces look like: CPPFLAGS="one two three"
                    formatted_value = self.single_value_format.format(" ".join(
                        chain(value, [placeholder])))
                else:
                    # Quoted variables joined with pathset may look like:
                    # PATH="one path":"two paths"
                    # Unquoted variables joined with pathset may look like: PATH=one path;two paths
                    formatted_value = self.path_separator.join(
                        chain(self.path_transform(value), [placeholder]))
            else:
                formatted_value = self.single_value_format.format(value)

            yield self.activate_value_format.format(
                name=name, value=formatted_value)

        yield self.activate_suffix

    def deactivate_lines(self):
        yield self.deactivate_prefix

        for name in self.env:
            yield self.deactivate_value_format.format(name=name)

        yield self.deactivate_suffix

    @abstractproperty
    def activate_prefix(self):
        raise NotImplementedError()

    activate_suffix = ""

    @abstractproperty
    def activate_value_format(self):
        raise NotImplementedError()

    @abstractproperty
    def single_value_format(self):
        raise NotImplementedError()

    @abstractproperty
    def placeholder_format(self):
        raise NotImplementedError()

    @abstractmethod
    def path_transform(self, values):
        raise NotImplementedError()

    @abstractproperty
    def path_separator(self):
        raise NotImplementedError()

    @abstractproperty
    def deactivate_prefix(self):
        raise NotImplementedError()

    @abstractproperty
    def deactivate_value_format(self):
        raise NotImplementedError()

    @abstractproperty
    def deactivate_suffix(self):
        raise NotImplementedError()


class PosixValueFormats(object):
    # NOTE: Maybe this should be a function which escapes internal quotes,
    # e.g. if some CXXFLAGS contain spaces and are quoted themselves.
    single_value_format = '"{}"'
    placeholder_format = "${}"
    path_separator = ":"

    def path_transform(self, values):
        return ('"%s"' % v for v in values)


class WindowsValueFormats(object):
    path_separator = os.pathsep
    """PowerShellCore on Linux and Mac uses colon as path separator"""

    def path_transform(self, values):
        return values


class FishScriptGenerator(PosixValueFormats, BasicScriptGenerator):
    def __init__(self, name, env):
        # Path is handled separately in fish.
        self.path = env.get("PATH", None)
        if "PATH" in env:
            env = env.copy()
            del env["PATH"]

        super(FishScriptGenerator, self).__init__(name, env)

    @property
    def activate_prefix(self):
        paths_prefix = dedent("""\
            if set -q fish_user_paths
                set -g _venv_old_fish_user_paths $fish_user_paths
            end
            set -g fish_user_paths %s $fish_user_paths
            """) % " ".join(self.path_transform(
            self.path)) if self.path else ""

        return dedent("""\
            if set -q venv_name
                deactivate
            end
            set -g venv_name "%s"

            functions -c fish_prompt _venv_old_fish_prompt

            function fish_prompt
                set -l old_status $status
                printf "%%s(%%s)%%s " (set_color green) $venv_name (set_color normal)
                # Restore the return status of the previous command.
                echo "exit $old_status" | .
                _venv_old_fish_prompt
            end

            %s""") % (self.name, paths_prefix)

    activate_value_format = dedent("""\
        if set -q {name}
            set -g _venv_old_{name} ${name}
        end
        set -gx {name} {value}""")

    @property
    def deactivate_prefix(self):
        paths_prefix = dedent("""\
            if set -q _venv_old_fish_user_paths
                set -g fish_user_paths $_venv_old_fish_user_paths
                set -e _venv_old_fish_user_paths
            else
                set -e fish_user_paths
            end""") if self.path else ""

        return dedent("""\
            function deactivate --description "Deactivate current virtualenv"

            functions -e fish_prompt
            functions -c _venv_old_fish_prompt fish_prompt
            functions -e _venv_old_fish_prompt

            %s
            """) % paths_prefix

    deactivate_suffix = dedent("""\
        set -e venv_name
        functions -e deactivate

        end
        """)

    deactivate_value_format = dedent("""\
        if set -q _venv_old_{name}
            set -gx {name} $_venv_old_{name}
            set -e _venv_old_{name}
        else
            set -ex {name}
        end
        """)


class ShScriptGenerator(PosixValueFormats, BasicScriptGenerator):
    def __init__(self, name, env):
        env = env.copy()
        env["PS1"] = "(%s) $PS1" % name
        super(ShScriptGenerator, self).__init__(name, env)

    @property
    def activate_prefix(self):
        return dedent("""\
            if [ -n "${VENV_NAME:-}" ] ; then
                deactivate
            fi
            VENV_NAME="%s"
            export VENV_NAME
            """) % self.name

    activate_value_format = dedent("""\
        if [ -n "${{{name}:-}}" ] ; then
            _venv_old_{name}="${{{name}}}"
        fi
        {name}={value}
        export {name}
        """)

    deactivate_prefix = dedent("""\
        deactivate () {
        """)

    deactivate_suffix = dedent("""\
        unset VENV_NAME
        unset -f deactivate

        }
        """)

    deactivate_value_format = dedent("""\
        if [ -n "${{_venv_old_{name}:-}}" ] ; then
            {name}="${{_venv_old_{name}:-}}"
            export {name}
            unset _venv_old_{name}
        else
            unset {name}
        fi
        """)


class PowerShellScriptGenerator(WindowsValueFormats, BasicScriptGenerator):
    single_value_format = "{}"
    placeholder_format = "$env:{}"

    @property
    def activate_prefix(self):
        return dedent("""\
            if (Test-Path env:VENV_NAME) {
                deactivate
            }
            $env:VENV_NAME = "%s"

            function global:_old_conan_prompt {""}
            $function:_old_conan_prompt = $function:prompt
            function global:prompt {
                Write-Host -NoNewline -ForegroundColor Green "($env:VENV_NAME) "
                _old_conan_prompt
            }
            """) % self.name

    activate_value_format = dedent("""\
        if (Test-Path env:{name}) {{
            $global:_venv_old_{name} = $env:{name}
        }}
        $env:{name} = "{value}"
        """)

    deactivate_prefix = dedent("""\
        function global:deactivate {
        if (Test-Path function:_old_conan_prompt) {
            $function:prompt = $function:_old_conan_prompt
            Remove-Item function:_old_conan_prompt
        }
        """)

    deactivate_suffix = dedent("""\
        Remove-Item env:VENV_NAME
        Remove-Item function:deactivate
        }
        """)

    deactivate_value_format = dedent("""\
        if (Test-Path variable:_venv_old_{name}) {{
            $env:{name} = $_venv_old_{name}
            Remove-Item variable:_venv_old_{name}
        }}
        else {{
            Remove-Item env:{name}
        }}
        """)


class CmdScriptGenerator(WindowsValueFormats, BasicScriptGenerator):
    single_value_format = "{}"
    placeholder_format = "%{}%"

    def __init__(self, name, env):
        env = env.copy()
        env["PROMPT"] = "(%s) %%PROMPT%%" % name
        super(CmdScriptGenerator, self).__init__(name, env)

    activate_prefix = "@echo off\n"
    activate_value_format = dedent("""\
        if defined {name} (
            set "_old_venv_{name}=%{name}%"
        )
        set {name}={value}
        """)

    deactivate_prefix = "@echo off\n"
    deactivate_suffix = ""

    deactivate_value_format = dedent("""\
        if defined _old_venv_{name} (
            set "{name}=%_old_venv_{name}%"
            set _old_venv_{name}=
        ) else (
            set {name}=
        )
        """)


class VirtualEnvGenerator(Generator):
    def __init__(self, conanfile):
        super(VirtualEnvGenerator, self).__init__(conanfile)
        self.env = conanfile.env
        self.venv_name = "conanenv"

    @property
    def filename(self):
        return

    @property
    def content(self):
        os_info = OSInfo()
        result = {}
        if os_info.is_windows and not os_info.is_posix:
            cmd_script = CmdScriptGenerator(self.venv_name, self.env)
            result["activate.bat"] = os.linesep.join(
                cmd_script.activate_lines())
            result["deactivate.bat"] = os.linesep.join(
                cmd_script.deactivate_lines())

        if os_info.is_posix:
            fish_script = FishScriptGenerator(self.venv_name, self.env)
            result["activate.fish"] = os.linesep.join(
                chain(fish_script.activate_lines(),
                      fish_script.deactivate_lines()))

        ps_script = PowerShellScriptGenerator(self.venv_name, self.env)
        result["activate.ps1"] = os.linesep.join(
            chain(ps_script.activate_lines(), ps_script.deactivate_lines()))

        sh_script = ShScriptGenerator(self.venv_name, self.env)
        result["activate.sh"] = os.linesep.join(
            chain(sh_script.activate_lines(), sh_script.deactivate_lines()))

        return result
