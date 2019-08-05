import os
import sys
from contextlib import contextmanager

from conans.client.run_environment import RunEnvironment
from conans.client.tools.files import _path_equals, which
from conans.errors import ConanException


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


def get_run_environment(conanfile):
    """
    :param conanfile: The ConanFile for which to construct an environment.

    :return: The changes applied to the current process environment, or None if unchanged.
    """
    env_vars, unset_vars = apply_environment(os.environ, RunEnvironment(conanfile).vars)

    if env_vars or unset_vars:
        new_env = os.environ.copy()
        new_env.update(env_vars)
        for var in unset_vars:
            new_env.pop(var, None)
        return new_env

    else:
        return None


@contextmanager
def run_environment(conanfile):
    with environment_append(RunEnvironment(conanfile).vars):
        yield


def apply_environment(env, env_vars):
    """
    :param env: The current environment.
    :param env_vars: List (dict) of simple environment vars. {name: value, name2: value2}
                     => e.g.: MYVAR=1
                     The values can also be lists of appendable environment vars.
                     {name: [value, value2]} => e.g. PATH=/path/1:/path/2
                     If the value is set to None, then that environment variable is unset.
    :return: The variables that need to be set and unset in the environment, respectively.
    """
    unset_vars = []
    for key in env_vars.keys():
        if env_vars[key] is None:
            unset_vars.append(key)
    for var in unset_vars:
        env_vars.pop(var, None)
    for name, value in env_vars.items():
        if isinstance(value, list):
            old = env.get(name)
            if old:
                value.append(old)
            env_vars[name] = os.pathsep.join(value)
    return env_vars, unset_vars


@contextmanager
def environment_append(env_vars):
    """
    :param env_vars: List (dict) of simple environment vars. {name: value, name2: value2}
                     => e.g.: MYVAR=1
                     The values can also be lists of appendable environment vars.
                     {name: [value, value2]} => e.g. PATH=/path/1:/path/2
                     If the value is set to None, then that environment variable is unset.
    :return: None
    """
    env_vars, unset_vars = apply_environment(os.environ, env_vars)
    if env_vars or unset_vars:
        old_env = dict(os.environ)
        os.environ.update(env_vars)
        for var in unset_vars:
            os.environ.pop(var, None)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(old_env)
    else:
        yield


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
