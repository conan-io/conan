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

    def get_str(self, placeholder, pathsep=os.pathsep):
        """
        :param placeholder: a OS dependant string pattern of the previous env-var value like
        $PATH, %PATH%, et
        :param pathsep: The path separator, typically ; or :
        :return: a string representation of the env-var value, including the $NAME-like placeholder
        """
        values = []
        for v in self._values:
            if v is _EnvVarPlaceHolder:
                if placeholder:
                    values.append(placeholder.format(name=self._name))
            else:
                values.append(v)
        if self._path:
            return pathsep.join(values)
        return self._sep.join(values)

    def get_value(self, pathsep=os.pathsep):
        previous_value = os.getenv(self._name)
        return self.get_str(previous_value, pathsep)


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

            """).format(filename=os.path.basename(filename), vars=" ".join(self._values.keys()))
        capture = textwrap.dedent("""\
            @echo off
            {deactivate}
            echo Configuring environment variables
            """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("%{name}%", pathsep)
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
            value = varvalues.get_str("$env:{name}", pathsep)
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
            """.format(filename=os.path.basename(filename), vars=" ".join(self._values.keys())))
        capture = textwrap.dedent("""\
           {deactivate}
           echo Configuring environment variables
           """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("${name}", pathsep)
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
                self._values[k] = v.copy()
            else:
                existing.compose(v)
        return self

    # Methods to user access to the environment object as a dict
    def keys(self):
        return self._values.keys()

    def __getitem__(self, name):
        return self._values[name].get_value()

    def get(self, name, default=None):
        v = self._values.get(name)
        if v is None:
            return default
        return v.get_value()

    def items(self):
        return {k: v.get_value() for k, v in self._values.items()}.items()

    def var(self, name):
        return self._values[name]

    def var_items(self):
        # Access to the dict items, so users can do what they want with the underlying env-var
        return self._values.items()

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


def save_script(conanfile, env, name):
    # FIXME: using platform is not ideal but settings might be incomplete
    if platform.system() == "Windows":
        complete_name = "{}.bat".format(name)
        path = os.path.join(conanfile.generators_folder, complete_name)
        env.save_bat(path)
    else:
        complete_name = "{}.sh".format(name)
        path = os.path.join(conanfile.generators_folder, complete_name)
        env.save_sh(path)

    conanfile.environment_scripts.append(complete_name)
