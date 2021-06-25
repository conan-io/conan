import fnmatch
import os
import textwrap
import platform
from collections import OrderedDict
from contextlib import contextmanager

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
            bats.append("{}.bat".format(full_path))
        elif os.path.isfile("{}.sh".format(full_path)):
            shs.append("{}.sh".format(full_path))
    if bats and shs:
        raise ConanException("Cannot wrap command with different envs, {} - {}".format(bats, shs))

    if bats:
        command = " && ".join('"{}"'.format(b) for b in bats)
        return "{} && {}".format(command, cmd)
    elif shs:
        curdir = "./" if cwd is None else ""
        command = " && ".join('. "{}{}"'.format(curdir, f) for f in shs)
        return "{} && {}".format(command, cmd)
    else:
        return cmd


class _EnvValue:
    def __init__(self, name, value=_EnvVarPlaceHolder, separator=" ", path=False):
        self._name = name
        self._values = [] if value is None else value if isinstance(value, list) else [value]
        self._path = path
        self._sep = separator

    def copy(self):
        return _EnvValue(self._name, self._values, self._sep, self._path)

    @property
    def is_path(self):
        return self._path

    def append(self, value, separator=None):
        if separator is not None:
            self._sep = separator
        if isinstance(value, list):
            self._values.extend(value)
        else:
            self._values.append(value)

    def prepend(self, value, separator=None):
        if separator is not None:
            self._sep = separator
        if isinstance(value, list):
            self._values = value + self._values
        else:
            self._values.insert(0, value)

    def compose(self, other):
        """
        :type other: _EnvValue
        """
        try:
            index = self._values.index(_EnvVarPlaceHolder)
        except ValueError:  # It doesn't have placeholder
            pass
        else:
            new_value = self._values[:]  # do a copy
            new_value[index:index + 1] = other._values  # replace the placeholder
            self._values = new_value

    def format_value(self, placeholder, pathsep):
        values = []
        for v in self._values:
            if v is _EnvVarPlaceHolder:
                values.append(placeholder.format(name=self._name))
            else:
                values.append(v)
        if self._path:
            return pathsep.join(values)
        return self._sep.join(values)


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
        return self._values[name].format_value(placeholder, pathsep)

    def define(self, name, value, separator=" "):
        self._values[name] = _EnvValue(name, value, separator, path=False)

    def define_path(self, name, value):
        self._values[name] = _EnvValue(name, value, path=True)

    def unset(self, name):
        """
        clears the variable, equivalent to a unset or set XXX=
        """
        self._values[name] = _EnvValue(name, None)

    def append(self, name, value, separator=None):
        self._values.setdefault(name, _EnvValue(name)).append(value, separator)

    def append_path(self, name, value):
        self._values.setdefault(name, _EnvValue(name, path=True)).append(value)

    def prepend(self, name, value, separator=None):
        self._values.setdefault(name, _EnvValue(name)).prepend(value, separator)

    def prepend_path(self, name, value):
        self._values.setdefault(name, _EnvValue(name, path=True)).prepend(value)

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
            value = varvalues.format_value("%{name}%", pathsep)
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
            value = varvalues.format_value("$env:{name}", pathsep)
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
            value = varvalues.format_value("${name}", pathsep)
            if value:
                result.append('export {}="{}"'.format(varname, value))
            else:
                result.append('unset {}'.format(varname))

        content = "\n".join(result)
        save(filename, content)

    def save_script(self, name):
        # FIXME: using platform is not ideal but settings might be incomplete
        if platform.system() == "Windows":
            self.save_bat("{}.bat".format(name))
        else:
            self.save_sh("{}.sh".format(name))

    def compose(self, other):
        """
        self has precedence, the "other" will add/append if possible and not conflicting, but
        self mandates what to do
        :type other: Environment
        """
        for k, v in other._values.items():
            existing = self._values.get(k)
            if existing is None:
                self._values[k] = v.copy()
            else:
                existing.compose(v)
        return self

    # Methods to user access to the environment object as a dict, replacing the placeholder with
    # the current environment value
    def _get_final_value(self, name):
        if name not in self._values:
            raise KeyError("No environment variable: " + name)
        previous_value = os.getenv(name) or ""
        return self._values[name].format_value(previous_value, os.pathsep)

    def __getitem__(self, name):
        return self._get_final_value(name)

    def get(self, name, default=None):
        try:
            return self._get_final_value(name)
        except KeyError:
            return default

    def keys(self):
        return self._values.keys()

    def items(self):
        for k in self._values.keys():
            yield k, self._get_final_value(k)

    def __eq__(self, other):
        """
        :type other: Environment
        """
        return other._values == self._values

    def __ne__(self, other):
        return not self.__eq__(other)

    @contextmanager
    def apply(self):
        apply_vars = self.items()
        old_env = dict(os.environ)
        os.environ.update(apply_vars)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(old_env)


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
