import os
import platform
import sys
from collections import OrderedDict
from contextlib import contextmanager

from conans.client.run_environment import RunEnvironment
from conans.client.tools.files import _path_equals, which
from conans.errors import ConanException
from conans.util.runners import check_output_runner


@contextmanager
def pythonpath(conanfile):
    python_path = conanfile.env.get("PYTHONPATH", None)
    if python_path:
        old_path = sys.path[:]
        if isinstance(python_path, list):
            sys.path.extend(python_path)
        else:
            sys.path.append(python_path)

        yield
        sys.path = old_path
    else:
        yield


@contextmanager
def run_environment(conanfile):
    with environment_append(RunEnvironment(conanfile).vars):
        yield


@contextmanager
def environment_append(env_vars):
    with _environment_add(env_vars, post=False):
        yield


@contextmanager
def _environment_add(env_vars, post=False):
    """
    :param env_vars: List (dict) of simple environment vars. {name: value, name2: value2}
                     => e.g.: MYVAR=1
                     The values can also be lists of appendable environment vars.
                     {name: [value, value2]} => e.g. PATH=/path/1:/path/2
                     If the value is set to None, then that environment variable is unset.
    :param post: if True, the environment is appended at the end, not prepended (only LISTS)
    :return: None
    """
    if not env_vars:
        yield
        return

    unset_vars = []
    apply_vars = {}
    for name, value in env_vars.items():
        if value is None:
            unset_vars.append(name)
        elif isinstance(value, list):
            apply_vars[name] = os.pathsep.join(value)
            old = os.environ.get(name)
            if old:
                if post:
                    apply_vars[name] = old + os.pathsep + apply_vars[name]
                else:
                    apply_vars[name] += os.pathsep + old
            # Remove possible duplicates, keeping the order of the remaining paths
            items = apply_vars[name].split(os.pathsep)
            apply_vars[name] = os.pathsep.join(OrderedDict.fromkeys(items))
        else:
            apply_vars[name] = value

    old_env = dict(os.environ)
    os.environ.update(apply_vars)
    for var in unset_vars:
        os.environ.pop(var, None)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


@contextmanager
def no_op():
    yield


@contextmanager
def remove_from_path(command):
    curpath = os.getenv("PATH")
    first_it = True
    for _ in range(30):
        if not first_it:
            with environment_append({"PATH": curpath}):
                the_command = which(command)
        else:
            the_command = which(command)
            first_it = False

        if not the_command:
            break
        new_path = []
        for entry in curpath.split(os.pathsep):
            if not _path_equals(entry, os.path.dirname(the_command)):
                new_path.append(entry)

        curpath = os.pathsep.join(new_path)
    else:
        raise ConanException("Error in tools.remove_from_path!! couldn't remove the tool '%s' "
                             "from the path after 30 attempts, still found in '%s' this is a "
                             "Conan client bug, please open an issue at: "
                             "https://github.com/conan-io/conan\n\nPATH=%s"
                             % (command, the_command, os.getenv("PATH")))

    with environment_append({"PATH": curpath}):
        yield


def env_diff(cmd, only_diff):
    known_path_lists = ("include", "lib", "libpath", "path")
    if platform.system() == "Windows":
        cmd += " && set"
    else:
        cmd += " && export"
    ret = check_output_runner(cmd)
    new_env = {}
    for line in ret.splitlines():
        line = line.strip()

        if line == "\n" or not line:
            continue
        try:
            name_var, value = line.split("=", 1)
            name_var = str(name_var)
            value = str(value)
            new_value = value.split(os.pathsep) if name_var.lower() in known_path_lists else value
            # Return only new vars & changed ones, but only with the changed elements if the var is
            # a list
            if only_diff:
                old_value = os.environ.get(name_var)
                if name_var.lower() == "path":
                    old_values_lower = [v.lower() for v in old_value.split(os.pathsep)]
                    # Clean all repeated entries, not append if the element was already there
                    new_env[name_var] = [v for v in new_value if v.lower() not in old_values_lower]
                elif old_value and value.endswith(os.pathsep + old_value):
                    # The new value ends with separator and the old value, is a list,
                    # get only the new elements
                    new_env[name_var] = value[:-(len(old_value) + 1)].split(os.pathsep)
                elif value != old_value:
                    # Only if the vcvars changed something, we return the variable,
                    # otherwise is not vcvars related
                    new_env[name_var] = new_value
            else:
                new_env[name_var] = new_value

        except ValueError:
            pass
    return new_env
