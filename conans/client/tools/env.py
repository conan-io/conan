import sys
from contextlib import contextmanager

import os

from conans.client.tools.files import which, _path_equals
from conans.errors import ConanException


@contextmanager
def pythonpath(conanfile):
    old_path = sys.path[:]
    python_path = conanfile.env.get("PYTHONPATH", None)
    if python_path:
        if isinstance(python_path, list):
            sys.path.extend(python_path)
        else:
            sys.path.append(python_path)

    yield
    sys.path = old_path


@contextmanager
def environment_append(env_vars):
    """
    :param env_vars: List of simple environment vars. {name: value, name2: value2} => e.j: MYVAR=1
                     The values can also be lists of appendable environment vars. {name: [value, value2]}
                      => e.j. PATH=/path/1:/path/2
    :return: None
    """
    old_env = dict(os.environ)
    for name, value in env_vars.items():
        if isinstance(value, list):
            env_vars[name] = os.pathsep.join(value)
            if name in old_env:
                env_vars[name] += os.pathsep + old_env[name]
    os.environ.update(env_vars)
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
    for n in range(30):
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
                             "from the path after 30 attempts, still found in '%s' this is a Conan client bug, please open an issue at: "
                             "https://github.com/conan-io/conan\n\nPATH=%s" % (command, the_command, os.getenv("PATH")))

    with environment_append({"PATH": curpath}):
        yield
