import fnmatch
import os
import textwrap
from collections import OrderedDict
from contextlib import contextmanager

from conans.client.subsystems import deduce_subsystem, WINDOWS, subsystem_path
from conans.errors import ConanException
from conans.util.files import save


class _EnvVarPlaceHolder:
    pass


def environment_wrap_command(env_filenames, env_folder, cmd, subsystem=None,
                             accepted_extensions=None):
    if not env_filenames:
        return cmd
    filenames = [env_filenames] if not isinstance(env_filenames, list) else env_filenames
    bats, shs, ps1s = [], [], []

    accept = accepted_extensions or ("ps1", "bat", "sh")
    # TODO: This implemantation is dirty, improve it
    for f in filenames:
        f = f if os.path.isabs(f) else os.path.join(env_folder, f)
        if f.lower().endswith(".sh"):
            if os.path.isfile(f) and "sh" in accept:
                f = subsystem_path(subsystem, f)
                shs.append(f)
        elif f.lower().endswith(".bat"):
            if os.path.isfile(f) and "bat" in accept:
                bats.append(f)
        elif f.lower().endswith(".ps1") and "ps1" in accept:
            if os.path.isfile(f):
                ps1s.append(f)
        else:  # Simple name like "conanrunenv"
            path_bat = "{}.bat".format(f)
            path_sh = "{}.sh".format(f)
            path_ps1 = "{}.ps1".format(f)
            if os.path.isfile(path_bat) and "bat" in accept:
                bats.append(path_bat)
            if os.path.isfile(path_ps1) and "ps1" in accept:
                ps1s.append(path_ps1)
            if os.path.isfile(path_sh) and "sh" in accept:
                path_sh = subsystem_path(subsystem, path_sh)
                shs.append(path_sh)

    if bool(bats) + bool(shs) + bool(ps1s) > 1:
        raise ConanException("Cannot wrap command with different envs,"
                             " {} - {} - {}".format(bats, shs, ps1s))

    if bats:
        launchers = " && ".join('"{}"'.format(b) for b in bats)
        return '{} && {}'.format(launchers, cmd)
    elif shs:
        launchers = " && ".join('. "{}"'.format(f) for f in shs)
        return '{} && {}'.format(launchers, cmd)
    elif ps1s:
        # TODO: at the moment it only works with path without spaces
        launchers = " ; ".join('{}'.format(f) for f in ps1s)
        return 'powershell.exe {} ; cmd /c {}'.format(launchers, cmd)
    else:
        return cmd


class _EnvValue:
    def __init__(self, name, value=_EnvVarPlaceHolder, separator=" ", path=False):
        self._name = name
        self._values = [] if value is None else value if isinstance(value, list) else [value]
        self._path = path
        self._sep = separator

    def dumps(self):
        result = []
        path = "(path)" if self._path else ""
        if not self._values:  # Empty means unset
            result.append("{}=!".format(self._name))
        elif _EnvVarPlaceHolder in self._values:
            index = self._values.index(_EnvVarPlaceHolder)
            for v in self._values[:index]:
                result.append("{}=+{}{}".format(self._name, path, v))
            for v in self._values[index+1:]:
                result.append("{}+={}{}".format(self._name, path, v))
        else:
            append = ""
            for v in self._values:
                result.append("{}{}={}{}".format(self._name, append, path, v))
                append = "+"
        return "\n".join(result)

    def copy(self):
        return _EnvValue(self._name, self._values, self._sep, self._path)

    @property
    def is_path(self):
        return self._path

    def remove(self, value):
        self._values.remove(value)

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

    def compose_env_value(self, other):
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

    def get_str(self, placeholder, subsystem, pathsep):
        """
        :param subsystem:
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
                if self._path:
                    v = subsystem_path(subsystem, v)
                values.append(v)
        if self._path:
            return pathsep.join(values)

        return self._sep.join(values)

    def get_value(self, subsystem, pathsep):
        previous_value = os.getenv(self._name)
        return self.get_str(previous_value, subsystem, pathsep)


class Environment:
    def __init__(self):
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()  # {var_name: [] of values, including separators}

    def __bool__(self):
        return bool(self._values)

    __nonzero__ = __bool__

    def copy(self):
        e = Environment()
        e._values = self._values.copy()
        return e

    def __repr__(self):
        return repr(self._values)

    def dumps(self):
        """ returns a string with a profile-like original definition, not the full environment
        values
        """
        return "\n".join([v.dumps() for v in reversed(self._values.values())])

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

    def remove(self, name, value):
        self._values[name].remove(value)

    def compose_env(self, other):
        """
        self has precedence, the "other" will add/append if possible and not conflicting, but
        self mandates what to do. If self has define(), without placeholder, that will remain
        :type other: Environment
        """
        for k, v in other._values.items():
            existing = self._values.get(k)
            if existing is None:
                self._values[k] = v.copy()
            else:
                existing.compose_env_value(v)

        return self

    def __eq__(self, other):
        """
        :type other: Environment
        """
        return other._values == self._values

    def __ne__(self, other):
        return not self.__eq__(other)

    def vars(self, conanfile, scope="build"):
        return EnvVars(conanfile, self, scope)


class EnvVars:
    def __init__(self, conanfile, env, scope):
        self._values = env._values  # {var_name: _EnvValue}, just a reference to the Environment
        self._conanfile = conanfile
        self._scope = scope
        self._subsystem = deduce_subsystem(conanfile, scope)

    @property
    def _pathsep(self):
        return ":" if self._subsystem != WINDOWS else ";"

    def __getitem__(self, name):
        return self._values[name].get_value(self._subsystem, self._pathsep)

    def keys(self):
        return self._values.keys()

    def get(self, name, default=None):
        v = self._values.get(name)
        if v is None:
            return default
        return v.get_value(self._subsystem, self._pathsep)

    def items(self):
        """returns {str: str} (varname: value)"""
        return {k: v.get_value(self._subsystem, self._pathsep)
                for k, v in self._values.items()}.items()

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

    def save_bat(self, file_location, generate_deactivate=True):
        filepath, filename = os.path.split(file_location)
        deactivate_file = os.path.join(filepath, "deactivate_{}".format(filename))
        deactivate = textwrap.dedent("""\
            echo Capturing current environment in {deactivate_file}
            setlocal
            echo @echo off > "{deactivate_file}"
            echo echo Restoring environment >> "{deactivate_file}"
            for %%v in ({vars}) do (
                set foundenvvar=
                for /f "delims== tokens=1,2" %%a in ('set') do (
                    if /I "%%a" == "%%v" (
                        echo set "%%a=%%b">> "{deactivate_file}"
                        set foundenvvar=1
                    )
                )
                if not defined foundenvvar (
                    echo set %%v=>> "{deactivate_file}"
                )
            )
            endlocal
            """).format(deactivate_file=deactivate_file, vars=" ".join(self._values.keys()))
        capture = textwrap.dedent("""\
            @echo off
            {deactivate}
            echo Configuring environment variables
            """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("%{name}%", subsystem=self._subsystem, pathsep=self._pathsep)
            result.append('set "{}={}"'.format(varname, value))

        content = "\n".join(result)
        save(file_location, content)

    def save_ps1(self, file_location, generate_deactivate=True,):
        filepath, filename = os.path.split(file_location)
        deactivate_file = os.path.join(filepath, "deactivate_{}".format(filename))
        deactivate = textwrap.dedent("""\
            echo "Capturing current environment in {deactivate_file}"

            "echo `"Restoring environment`"" | Out-File -FilePath "{deactivate_file}"
            $vars = (Get-ChildItem env:*).name
            $updated_vars = @({vars})

            foreach ($var in $updated_vars)
            {{
                if ($var -in $vars)
                {{
                    $var_value = (Get-ChildItem env:$var).value
                    Add-Content "{deactivate_file}" "`n`$env:$var = `"$var_value`""
                }}
                else
                {{
                    Add-Content "{deactivate_file}" "`nif (Test-Path env:$var) {{ Remove-Item env:$var }}"
                }}
            }}
        """).format(
            deactivate_file=deactivate_file,
            vars=",".join(['"{}"'.format(var) for var in self._values.keys()])
        )

        capture = textwrap.dedent("""\
            {deactivate}
            echo "Configuring environment variables"
        """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("$env:{name}", subsystem=self._subsystem, pathsep=self._pathsep)
            if value:
                value = value.replace('"', '`"')  # escape quotes
                result.append('$env:{}="{}"'.format(varname, value))
            else:
                result.append('if (Test-Path env:{0}) {{ Remove-Item env:{0} }}'.format(varname))

        content = "\n".join(result)
        save(file_location, content)

    def save_sh(self, file_location, generate_deactivate=True):
        filepath, filename = os.path.split(file_location)
        deactivate_file = os.path.join(filepath, "deactivate_{}".format(filename))
        deactivate = textwrap.dedent("""\
           echo Capturing current environment in "{deactivate_file}"
           echo "echo Restoring environment" >> "{deactivate_file}"
           for v in {vars}
           do
               is_defined="true"
               value=$(printenv $v) || is_defined="" || true
               if [ -n "$value" ] || [ -n "$is_defined" ]
               then
                   echo export "$v='$value'" >> "{deactivate_file}"
               else
                   echo unset $v >> "{deactivate_file}"
               fi
           done
           """.format(deactivate_file=deactivate_file, vars=" ".join(self._values.keys())))
        capture = textwrap.dedent("""\
              {deactivate}
              echo Configuring environment variables
              """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("${name}", self._subsystem, pathsep=self._pathsep)
            value = value.replace('"', '\\"')
            if value:
                result.append('export {}="{}"'.format(varname, value))
            else:
                result.append('unset {}'.format(varname))

        content = "\n".join(result)
        save(file_location, content)

    def save_script(self, filename):
        name, ext = os.path.splitext(filename)
        if ext:
            is_bat = ext == ".bat"
            is_ps1 = ext == ".ps1"
        else:  # Need to deduce it automatically
            is_bat = self._subsystem == WINDOWS
            is_ps1 = self._conanfile.conf.get("tools.env.virtualenv:powershell", check_type=bool)
            if is_ps1:
                filename = filename + ".ps1"
                is_bat = False
            else:
                filename = filename + (".bat" if is_bat else ".sh")

        path = os.path.join(self._conanfile.generators_folder, filename)
        if is_bat:
            self.save_bat(path)
        elif is_ps1:
            self.save_ps1(path)
        else:
            self.save_sh(path)

        if self._scope:
            register_env_script(self._conanfile, path, self._scope)


class ProfileEnvironment:
    def __init__(self):
        self._environments = OrderedDict()

    def __repr__(self):
        return repr(self._environments)

    def __bool__(self):
        return bool(self._environments)

    __nonzero__ = __bool__

    def get_profile_env(self, ref):
        """ computes package-specific Environment
        it is only called when conanfile.buildenv is called
        the last one found in the profile file has top priority
        """
        result = Environment()
        for pattern, env in self._environments.items():
            if pattern is None or fnmatch.fnmatch(str(ref), pattern):
                # Latest declared has priority, copy() necessary to not destroy data
                result = env.copy().compose_env(result)
        return result

    def update_profile_env(self, other):
        """
        :type other: ProfileEnvironment
        :param other: The argument profile has priority/precedence over the current one.
        """
        for pattern, environment in other._environments.items():
            existing = self._environments.get(pattern)
            if existing is not None:
                self._environments[pattern] = environment.compose_env(existing)
            else:
                self._environments[pattern] = environment

    def dumps(self):
        result = []
        for pattern, env in self._environments.items():
            if pattern is None:
                result.append(env.dumps())
            else:
                result.append("\n".join("{}:{}".format(pattern, line) if line else ""
                                        for line in env.dumps().splitlines()))
        if result:
            result.append("")
        return "\n".join(result)

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

                # strip whitespaces before/after =
                # values are not strip() unless they are a path, to preserve potential whitespaces
                name = name.strip()

                # When loading from profile file, latest line has priority
                env = Environment()
                if method == "unset":
                    env.unset(name)
                else:
                    if value.strip().startswith("(path)"):
                        value = value.strip()
                        value = value[6:]
                        method = method + "_path"
                    getattr(env, method)(name, value)

                existing = result._environments.get(pattern)
                if existing is None:
                    result._environments[pattern] = env
                else:
                    result._environments[pattern] = env.compose_env(existing)
                break
            else:
                raise ConanException("Bad env definition: {}".format(line))
        return result


def create_env_script(conanfile, content, filename, scope):
    """
    Create a file with any content which will be registered as a new script for the defined "group".
    """
    path = os.path.join(conanfile.generators_folder, filename)
    save(path, content)

    if scope:
        register_env_script(conanfile, path, scope)


def register_env_script(conanfile, env_script_path, scope):
    """
    Add the "env_script_path" to the current list of registered scripts for defined "group"
    These will be mapped to files:
    - conan{group}.bat|sh = calls env_script_path1,... env_script_pathN
    """
    existing = conanfile.env_scripts.setdefault(scope, [])
    if env_script_path not in existing:
        existing.append(env_script_path)
