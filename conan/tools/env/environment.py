import fnmatch
import os
import textwrap
from collections import OrderedDict

from conans.errors import ConanException
from conans.util.files import save


class _EnvVarPlaceHolder:
    pass


class _Sep(str):
    pass


class _PathSep:
    pass


def environment_wrap_command(filename, cmd, cwd=None):
    assert filename
    filenames = [filename] if not isinstance(filename, list) else filename
    bats, shs = [], []
    for f in filenames:
        full_path = os.path.join(cwd, f) if cwd else f
        if os.path.isfile("{}.bat".format(full_path)):
            bats.append("{}.bat".format(f))
        elif os.path.isfile("{}.sh".format(full_path)):
            shs.append("{}.sh".format(f))
    if bats and shs:
        raise ConanException("Cannot wrap command with different envs, {} - {}".format(bats, shs))

    if bats:
        command = " && ".join(bats)
        return "{} && {}".format(command, cmd)
    elif shs:
        command = " && ".join(". ./{}".format(f) for f in shs)
        return "{} && {}".format(command, cmd)
    else:
        return cmd


class Environment:
    def __init__(self):
        # TODO: Maybe we need to pass conanfile to get the [conf]
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()  # {var_name: [] of values, including separators}

    def __bool__(self):
        return bool(self._values)

    __nonzero__ = __bool__

    def __repr__(self):
        return repr(self._values)

    def vars(self):
        return list(self._values.keys())

    def value(self, name, placeholder="{name}", pathsep=os.pathsep):
        return self._format_value(name, self._values[name], placeholder, pathsep)

    @staticmethod
    def _format_value(name, varvalues, placeholder, pathsep):
        values = []
        for v in varvalues:

            if v is _EnvVarPlaceHolder:
                values.append(placeholder.format(name=name))
            elif v is _PathSep:
                values.append(pathsep)
            else:
                values.append(v)
        return "".join(values)

    @staticmethod
    def _list_value(value, separator):
        if isinstance(value, list):
            result = []
            for v in value[:-1]:
                result.append(v)
                result.append(separator)
            result.extend(value[-1:])
            return result
        else:
            return [value]

    def define(self, name, value, separator=" "):
        value = self._list_value(value, _Sep(separator))
        self._values[name] = value

    def define_path(self, name, value):
        value = self._list_value(value, _PathSep)
        self._values[name] = value

    def unset(self, name):
        """
        clears the variable, equivalent to a unset or set XXX=
        """
        self._values[name] = []

    def append(self, name, value, separator=" "):
        value = self._list_value(value, _Sep(separator))
        self._values[name] = [_EnvVarPlaceHolder] + [_Sep(separator)] + value

    def append_path(self, name, value):
        value = self._list_value(value, _PathSep)
        self._values[name] = [_EnvVarPlaceHolder] + [_PathSep] + value

    def prepend(self, name, value, separator=" "):
        value = self._list_value(value, _Sep(separator))
        self._values[name] = value + [_Sep(separator)] + [_EnvVarPlaceHolder]

    def prepend_path(self, name, value):
        value = self._list_value(value, _PathSep)
        self._values[name] = value + [_PathSep] + [_EnvVarPlaceHolder]

    def save_bat(self, filename, generate_deactivate=False, pathsep=os.pathsep):
        deactivate = textwrap.dedent("""\
            echo Capturing current environment in deactivate_{filename}
            setlocal
            echo @echo off > "deactivate_{filename}"
            echo echo Restoring environment >> "deactivate_{filename}"
            for %%v in ({vars}) do (
                set foundenvvar=
                for /f "delims== tokens=1,2" %%a in ('set') do (
                    if "%%a" == "%%v" (
                        echo set %%a=%%b>> "deactivate_{filename}"
                        set foundenvvar=1
                    )
                )
                if not defined foundenvvar (
                    echo set %%v=>> "deactivate_{filename}"
                )
            )
            endlocal

            """).format(filename=filename, vars=" ".join(self._values.keys()))
        capture = textwrap.dedent("""\
            @echo off
            {deactivate}
            echo Configuring environment variables
            """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = self._format_value(varname, varvalues, "%{name}%", pathsep)
            result.append('set {}={}'.format(varname, value))

        content = "\n".join(result)
        save(filename, content)

    def save_ps1(self, filename, generate_deactivate=False, pathsep=os.pathsep):
        # FIXME: This is broken and doesnt work
        deactivate = ""
        capture = textwrap.dedent("""\
            {deactivate}
            """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = self._format_value(varname, varvalues, "$env:{name}", pathsep)
            result.append('$env:{}={}'.format(varname, value))

        content = "\n".join(result)
        save(filename, content)

    def save_sh(self, filename, generate_deactivate=False, pathsep=os.pathsep):
        deactivate = textwrap.dedent("""\
            echo Capturing current environment in deactivate_{filename}
            echo echo Restoring variables >> deactivate_{filename}
            for v in {vars}
            do
                value=$(printenv $v)
                if [ -n "$value" ]
                then
                    echo export "$v=$value" >> deactivate_{filename}
                else
                    echo unset $v >> deactivate_{filename}
                fi
            done
            echo Configuring environment variables
            """.format(filename=filename, vars=" ".join(self._values.keys())))
        capture = textwrap.dedent("""\
           {deactivate}
           echo Configuring environment variables
           """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = self._format_value(varname, varvalues, "${name}", pathsep)
            if value:
                result.append('export {}="{}"'.format(varname, value))
            else:
                result.append('unset {}'.format(varname))

        content = "\n".join(result)
        save(filename, content)

    def compose(self, other):
        """
        self has precedence, the "other" will add/append if possible and not conflicting, but
        self mandates what to do
        :type other: Environment
        """
        for k, v in other._values.items():
            existing = self._values.get(k)
            if existing is None:
                self._values[k] = v
            else:
                try:
                    index = existing.index(_EnvVarPlaceHolder)
                except ValueError:  # It doesn't have placeholder
                    pass
                else:
                    new_value = existing[:]  # do a copy
                    new_value[index:index + 1] = v  # replace the placeholder
                    # Trim front and back separators
                    val = new_value[0]
                    if isinstance(val, _Sep) or val is _PathSep:
                        new_value = new_value[1:]
                    val = new_value[-1]
                    if isinstance(val, _Sep) or val is _PathSep:
                        new_value = new_value[:-1]
                    self._values[k] = new_value
        return self


class ProfileEnvironment:
    def __init__(self):
        self._environments = OrderedDict()

    def __repr__(self):
        return repr(self._environments)

    def get_env(self, ref):
        """ computes package-specific Environment
        it is only called when conanfile.buildenv is called
        the last one found in the profile file has top priority
        """
        result = Environment()
        for pattern, env in self._environments.items():
            if pattern is None or fnmatch.fnmatch(str(ref), pattern):
                result = env.compose(result)
        return result

    def compose(self, other):
        """
        :type other: ProfileEnvironment
        """
        for pattern, environment in other._environments.items():
            existing = self._environments.get(pattern)
            if existing is not None:
                self._environments[pattern] = environment.compose(existing)
            else:
                self._environments[pattern] = environment

    @staticmethod
    def loads(text):
        result = ProfileEnvironment()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for op, method in (("+=", "append"), ("=+", "prepend"),
                               ("=!", "unset"), ("=", "define")):
                tokens = line.split(op, 1)
                if len(tokens) != 2:
                    continue
                pattern_name, value = tokens
                pattern_name = pattern_name.split(":", 1)
                if len(pattern_name) == 2:
                    pattern, name = pattern_name
                else:
                    pattern, name = None, pattern_name[0]

                env = Environment()
                if method == "unset":
                    env.unset(name)
                else:
                    if value.startswith("(path)"):
                        value = value[6:]
                        method = method + "_path"
                    getattr(env, method)(name, value)

                existing = result._environments.get(pattern)
                if existing is None:
                    result._environments[pattern] = env
                else:
                    result._environments[pattern] = env.compose(existing)
                break
            else:
                raise ConanException("Bad env defintion: {}".format(line))
        return result
