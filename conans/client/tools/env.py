import sys
from contextlib import contextmanager

import os


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
