import os
import textwrap
from collections import OrderedDict
from contextlib import contextmanager

from conans.client.generators import relativize_paths
from conans.client.subsystems import deduce_subsystem, WINDOWS, subsystem_path
from conan.errors import ConanException
from conans.model.recipe_ref import ref_matches
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

    if bool(bats + ps1s) + bool(shs) > 1:
        raise ConanException("Cannot wrap command with different envs,"
                             "{} - {}".format(bats+ps1s, shs))

    if bats:
        launchers = " && ".join('"{}"'.format(b) for b in bats)
        if ps1s:
            ps1_launchers = " ; ".join('"&\'{}\'"'.format(f) for f in ps1s)
            cmd = cmd.replace('"', "'")
            return '{} && powershell.exe {} ; cmd /c {}'.format(launchers, ps1_launchers, cmd)
        else:
            return '{} && {}'.format(launchers, cmd)
    elif shs:
        launchers = " && ".join('. "{}"'.format(f) for f in shs)
        return '{} && {}'.format(launchers, cmd)
    elif ps1s:
        # TODO: at the moment it only works with path without spaces
        launchers = " ; ".join('"&\'{}\'"'.format(f) for f in ps1s)
        cmd = cmd.replace('"', "'")
        return 'powershell.exe {} ; cmd /c {}'.format(launchers, cmd)
    else:
        return cmd


class _EnvValue:
    def __init__(self, name, value=None, separator=" ", path=False):
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

    def get_str(self, placeholder, subsystem, pathsep, root_path=None, script_path=None):
        """
        :param subsystem:
        :param placeholder: a OS dependant string pattern of the previous env-var value like
        $PATH, %PATH%, et
        :param pathsep: The path separator, typically ; or :
        :param root_path: To do a relativize of paths, the base root path to be replaced
        :param script_path: the replacement instead of the script path
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
                    if root_path is not None:
                        if v.startswith(root_path):  # relativize
                            v = v.replace(root_path, script_path, 1)
                        elif os.sep == "\\":  # Just in case user specified C:/path/to/somewhere
                            r = root_path.replace("\\", "/")
                            if v.startswith(r):
                                v = v.replace(r, script_path.replace("\\", "/"))
                values.append(v)
        if self._path:
            return pathsep.join(values)

        return self._sep.join(values)

    def get_value(self, subsystem, pathsep):
        previous_value = os.getenv(self._name)
        return self.get_str(previous_value, subsystem, pathsep)

    def deploy_base_folder(self, package_folder, deploy_folder):
        """Make the path relative to the deploy_folder"""
        if not self._path:
            return
        for i, v in enumerate(self._values):
            if v is _EnvVarPlaceHolder:
                continue
            rel_path = os.path.relpath(v, package_folder)
            if rel_path.startswith(".."):
                # If it is pointing to a folder outside of the package, then do not relocate
                continue
            self._values[i] = os.path.join(deploy_folder, rel_path)

    def set_relative_base_folder(self, folder):
        if not self._path:
            return
        self._values = [os.path.join(folder, v) if v != _EnvVarPlaceHolder else v
                        for v in self._values]


class Environment:
    """
    Generic class that helps to define modifications to the environment variables.
    """

    def __init__(self):
        # It being ordered allows for Windows case-insensitive composition
        self._values = OrderedDict()  # {var_name: [] of values, including separators}

    def __bool__(self):
        return bool(self._values)

    def copy(self):
        e = Environment()
        # TODO: Check this, the internal list is not being copied
        e._values = self._values.copy()
        return e

    def __repr__(self):
        return repr(self._values)

    def dumps(self):

        """
        :return: A string with a profile-like original definition, not the full environment
                 values
        """
        return "\n".join([v.dumps() for v in reversed(self._values.values())])

    def define(self, name, value, separator=" "):
        """
        Define `name` environment variable with value `value`

        :param name: Name of the variable
        :param value: Value that the environment variable will take
        :param separator: The character to separate appended or prepended values
        """
        self._values[name] = _EnvValue(name, value, separator, path=False)

    def define_path(self, name, value):
        self._values[name] = _EnvValue(name, value, path=True)

    def unset(self, name):
        """
        clears the variable, equivalent to a unset or set XXX=

        :param name: Name of the variable to unset
        """
        self._values[name] = _EnvValue(name, None)

    def append(self, name, value, separator=None):
        """
        Append the `value` to an environment variable `name`

        :param name: Name of the variable to append a new value
        :param value: New value
        :param separator: The character to separate the appended value with the previous value. By default it will use a blank space.
        """
        self._values.setdefault(name, _EnvValue(name, _EnvVarPlaceHolder)).append(value, separator)

    def append_path(self, name, value):
        """
        Similar to "append" method but indicating that the variable is a filesystem path. It will automatically handle the path separators depending on the operating system.

        :param name: Name of the variable to append a new value
        :param value: New value
        """
        self._values.setdefault(name, _EnvValue(name, _EnvVarPlaceHolder, path=True)).append(value)

    def prepend(self, name, value, separator=None):
        """
        Prepend the `value` to an environment variable `name`

        :param name: Name of the variable to prepend a new value
        :param value: New value
        :param separator: The character to separate the prepended value with the previous value
        """
        self._values.setdefault(name, _EnvValue(name, _EnvVarPlaceHolder)).prepend(value, separator)

    def prepend_path(self, name, value):
        """
        Similar to "prepend" method but indicating that the variable is a filesystem path. It will automatically handle the path separators depending on the operating system.

        :param name: Name of the variable to prepend a new value
        :param value: New value
        """
        self._values.setdefault(name, _EnvValue(name, _EnvVarPlaceHolder, path=True)).prepend(value)

    def remove(self, name, value):
        """
        Removes the `value` from the variable `name`.

        :param name: Name of the variable
        :param value: Value to be removed.
        """
        self._values[name].remove(value)

    def compose_env(self, other):
        """
        Compose an Environment object with another one.
        ``self`` has precedence, the "other" will add/append if possible and not
        conflicting, but ``self`` mandates what to do. If ``self`` has ``define()``, without
        placeholder, that will remain.

        :param other: the "other" Environment
        :type other: class:`Environment`
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
        :param other: the "other" environment
        :type other: class:`Environment`
        """
        return other._values == self._values

    def vars(self, conanfile, scope="build"):
        """
        Return an EnvVars object from the current Environment object
        :param conanfile: Instance of a conanfile, usually ``self`` in a recipe
        :param scope: Determine the scope of the declared variables.
        :return:
        """
        return EnvVars(conanfile, self._values, scope)

    def deploy_base_folder(self, package_folder, deploy_folder):
        """Make the paths relative to the deploy_folder"""
        for varvalues in self._values.values():
            varvalues.deploy_base_folder(package_folder, deploy_folder)

    def set_relative_base_folder(self, folder):
        for v in self._values.values():
            v.set_relative_base_folder(folder)


class EnvVars:
    """
    Represents an instance of environment variables for a given system. It is obtained from the generic Environment class.

    """
    def __init__(self, conanfile, values, scope):
        self._values = values  # {var_name: _EnvValue}, just a reference to the Environment
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

    def get(self, name, default=None, variable_reference=None):
        """ get the value of a env-var

        :param name: The name of the environment variable.
        :param default: The returned value if the variable doesn't exist, by default None.
        :param variable_reference: if specified, use a variable reference instead of the
                                   pre-existing value of environment variable, where {name}
                                   can be used to refer to the name of the variable.
        """
        v = self._values.get(name)
        if v is None:
            return default
        if variable_reference:
            return v.get_str(variable_reference, self._subsystem, self._pathsep)
        else:
            return v.get_value(self._subsystem, self._pathsep)

    def items(self, variable_reference=None):
        """returns {str: str} (varname: value)

        :param variable_reference: if specified, use a variable reference instead of the
                                   pre-existing value of environment variable, where {name}
                                   can be used to refer to the name of the variable.
        """
        if variable_reference:
            return {k: v.get_str(variable_reference, self._subsystem, self._pathsep)
                    for k, v in self._values.items()}.items()
        else:
            return {k: v.get_value(self._subsystem, self._pathsep)
                    for k, v in self._values.items()}.items()

    @contextmanager
    def apply(self):
        """
        Context manager to apply the declared variables to the current ``os.environ`` restoring
        the original environment when the context ends.

        """
        apply_vars = self.items()
        old_env = dict(os.environ)
        os.environ.update(apply_vars)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(old_env)

    def save_bat(self, file_location, generate_deactivate=True):
        _, filename = os.path.split(file_location)
        deactivate_file = "deactivate_{}".format(filename)
        deactivate = textwrap.dedent("""\
            setlocal
            echo @echo off > "%~dp0/{deactivate_file}"
            echo echo Restoring environment >> "%~dp0/{deactivate_file}"
            for %%v in ({vars}) do (
                set foundenvvar=
                for /f "delims== tokens=1,2" %%a in ('set') do (
                    if /I "%%a" == "%%v" (
                        echo set "%%a=%%b">> "%~dp0/{deactivate_file}"
                        set foundenvvar=1
                    )
                )
                if not defined foundenvvar (
                    echo set %%v=>> "%~dp0/{deactivate_file}"
                )
            )
            endlocal
            """).format(deactivate_file=deactivate_file, vars=" ".join(self._values.keys()))
        capture = textwrap.dedent("""\
            @echo off
            chcp 65001 > nul
            {deactivate}
            """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        abs_base_path, new_path = relativize_paths(self._conanfile, "%~dp0")
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("%{name}%", subsystem=self._subsystem, pathsep=self._pathsep,
                                      root_path=abs_base_path, script_path=new_path)
            result.append('set "{}={}"'.format(varname, value))

        content = "\n".join(result)
        # It is very important to save it correctly with utf-8, the Conan util save() is broken
        os.makedirs(os.path.dirname(os.path.abspath(file_location)), exist_ok=True)
        open(file_location, "w", encoding="utf-8").write(content)

    def save_ps1(self, file_location, generate_deactivate=True,):
        _, filename = os.path.split(file_location)
        deactivate_file = "deactivate_{}".format(filename)
        deactivate = textwrap.dedent("""\
            Push-Location $PSScriptRoot
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
            Pop-Location
        """).format(
            deactivate_file=deactivate_file,
            vars=",".join(['"{}"'.format(var) for var in self._values.keys()])
        )

        capture = textwrap.dedent("""\
            {deactivate}
        """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        abs_base_path, new_path = relativize_paths(self._conanfile, "$PSScriptRoot")
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("$env:{name}", subsystem=self._subsystem, pathsep=self._pathsep,
                                      root_path=abs_base_path, script_path=new_path)
            if value:
                value = value.replace('"', '`"')  # escape quotes
                result.append('$env:{}="{}"'.format(varname, value))
            else:
                result.append('if (Test-Path env:{0}) {{ Remove-Item env:{0} }}'.format(varname))

        content = "\n".join(result)
        # It is very important to save it correctly with utf-16, the Conan util save() is broken
        # and powershell uses utf-16 files!!!
        os.makedirs(os.path.dirname(os.path.abspath(file_location)), exist_ok=True)
        open(file_location, "w", encoding="utf-16").write(content)

    def save_sh(self, file_location, generate_deactivate=True):
        filepath, filename = os.path.split(file_location)
        deactivate_file = os.path.join("$script_folder", "deactivate_{}".format(filename))
        deactivate = textwrap.dedent("""\
           echo "echo Restoring environment" > "{deactivate_file}"
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
              """).format(deactivate=deactivate if generate_deactivate else "")
        result = [capture]
        abs_base_path, new_path = relativize_paths(self._conanfile, "$script_folder")
        for varname, varvalues in self._values.items():
            value = varvalues.get_str("${name}", self._subsystem, pathsep=self._pathsep,
                                      root_path=abs_base_path, script_path=new_path)
            value = value.replace('"', '\\"')
            if value:
                result.append('export {}="{}"'.format(varname, value))
            else:
                result.append('unset {}'.format(varname))

        content = "\n".join(result)
        content = f'script_folder="{os.path.abspath(filepath)}"\n' + content
        save(file_location, content)

    def save_script(self, filename):
        """
        Saves a script file (bat, sh, ps1) with a launcher to set the environment.
        If the conf "tools.env.virtualenv:powershell" is set to True it will generate powershell
        launchers if Windows.

        :param filename: Name of the file to generate. If the extension is provided, it will generate
                         the launcher script for that extension, otherwise the format will be deduced
                         checking if we are running inside Windows (checking also the subsystem) or not.
        """
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

    def get_profile_env(self, ref, is_consumer=False):
        """ computes package-specific Environment
        it is only called when conanfile.buildenv is called
        the last one found in the profile file has top priority
        """
        result = Environment()
        for pattern, env in self._environments.items():
            if pattern is None or ref_matches(ref, pattern, is_consumer):
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
