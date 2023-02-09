"""
    Get variables from environment.
    Automatically handle types inferring datatype from default value.

    Usage:
        get_env('CONAN_SSL_ENABLED', False) => Will autotransform ENV CONAN_SSL_ENABLED to boolean

"""
import os
from contextlib import contextmanager


@contextmanager
def environment_update(env_vars):
    old_env = dict(os.environ)
    sets = {k: v for k, v in env_vars.items() if v is not None}
    unsets = [k for k, v in env_vars.items() if v is None]
    os.environ.update(sets)
    for var in unsets:
        os.environ.pop(var, None)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)


@contextmanager
def no_op():
    yield


def get_env(env_key, default=None, environment=None):
    """Get the env variable associated with env_key"""
    if environment is None:
        environment = os.environ

    env_var = environment.get(env_key, default)
    if env_var != default:
        if isinstance(default, str):
            return env_var
        elif isinstance(default, bool):
            return env_var == "1" or env_var == "True"
        elif isinstance(default, int):
            return int(env_var)
        elif isinstance(default, float):
            return float(env_var)
        elif isinstance(default, list):
            if env_var.strip():
                return [var.strip() for var in env_var.split(",")]
            return []
    return env_var
