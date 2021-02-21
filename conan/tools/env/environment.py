import fnmatch
import os
import textwrap
from collections import OrderedDict

from conans.errors import ConanException
from conans.util.files import save

_ENV_VAR_PLACEHOLDER = "$PREVIOUS_ENV_VAR_VALUE%"
_PATHSEP = "$CONAN_PATHSEP%"


class Environment:
    def __init__(self):
        # TODO: Maybe we need to pass conanfile to get the [conf]
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()  # {var_name: [] of values, including separators}

    def vars(self):
        return list(self._values.keys())

    def value(self, name, placeholder="{}", pathsep=os.pathsep):
        return self._format_value(name, self._values[name], placeholder, pathsep)

    @staticmethod
    def _format_value(name, varvalues, placeholder, pathsep):
        values = []
        for v in varvalues:
            if v == _ENV_VAR_PLACEHOLDER:
                values.append(placeholder.format(name=name))
            elif v == _PATHSEP:
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
        value = self._list_value(value, separator)
        self._values[name] = value

    def define_path(self, name, value):
        self.define(name, value, _PATHSEP)

    def unset(self, name):
        """
        clears the variable, equivalent to a unset or set XXX=
        """
        self._values[name] = []

    def append(self, name, value, separator=" "):
        value = self._list_value(value, separator)
        self._values[name] = [_ENV_VAR_PLACEHOLDER] + [separator] + value

    def append_path(self, name, value):
        self.append(name, value, _PATHSEP)

    def prepend(self, name, value, separator=" "):
        value = self._list_value(value, separator)
        self._values[name] = value + [separator] + [_ENV_VAR_PLACEHOLDER]

    def prepend_path(self, name, value):
        self.prepend(name, value, _PATHSEP)

    def save_bat(self, filename, generate_deactivate=True, pathsep=os.pathsep):
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

    def save_ps1(self, filename, generate_deactivate=True, pathsep=os.pathsep):
        # FIXME: This is broken and doesnt work
        deactivate = ""
        capture = textwrap.dedent("""\
            {deactivate}
            """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = self._format_value(varname, varvalues, "$env:{name}", pathsep)
            result.append('Write-Output "Error: whatever message {}"'.format(varname))
            result.append('$env:{}={}'.format(varname, value))

        content = "\n".join(result)
        save(filename, content)

    def save_sh(self, filename, pathsep=os.pathsep):
        capture = textwrap.dedent("""\
            echo Capturing current environment in deactivate_{filename}
            echo echo Restoring variables >> deactivate_{filename}
            for v in {vars}
            do
                value=${{!v}}
                if [ -n "$value" ]
                then
                    echo export "$v=$value" >> deactivate_{filename}
                else
                    echo unset $v >> deactivate_{filename}
                fi
            done
            echo Configuring environment variables
            """.format(filename=filename, vars=" ".join(self._values.keys())))
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
        :type other: Environment
        """
        for k, v in other._values.items():
            existing = self._values.get(k)
            if existing is None:
                self._values[k] = v
            else:
                try:
                    index = v.index(_ENV_VAR_PLACEHOLDER)
                except ValueError:  # The other doesn't have placeholder, overwrites
                    self._values[k] = v
                else:
                    new_value = v[:]  # do a copy
                    new_value[index:index + 1] = existing  # replace the placeholder
                    self._values[k] = new_value

        return self


class ProfileEnvironment:
    def __init__(self):
        self._environments = OrderedDict()

    def get_env(self, ref):
        # TODO: Maybe we want to make this lazy, so this is not evaluated for every package
        result = Environment()
        for pattern, env in self._environments.items():
            if pattern is None or fnmatch.fnmatch(str(ref), pattern):
                env = self._environments[pattern]
                result = result.compose(env)
        return result

    def compose(self, other):
        """
        :type other: ProfileEnvironment
        """
        for pattern, environment in other._environments.items():
            existing = self._environments.get(pattern)
            if existing is not None:
                self._environments[pattern] = existing.compose(environment)
            else:
                self._environments[pattern] = environment

    def loads(self, text):
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

                existing = self._environments.get(pattern)
                if existing is None:
                    self._environments[pattern] = env
                else:
                    self._environments[pattern] = existing.compose(env)
                break
            else:
                raise ConanException("Bad env defintion: {}".format(line))
