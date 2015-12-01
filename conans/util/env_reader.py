"""
    Get variables from environment.
    Automatically handle types inferring datatype from default value.

    Usage:
        get_env('CONAN_SSL_ENABLED', False) => Will autotransform ENV CONAN_SSL_ENABLED to boolean

"""
from types import NoneType
import os


def get_env(env_key, default=None, environment=os.environ):
    '''Get the env variable associated with env_key'''
    _default_type = {str: lambda x: x,
                NoneType: lambda x: x,
                int: lambda x: int(x),
                float: lambda x: float(x),
                list: lambda x: x.split(","),
                bool: lambda x: x == '1'}

    env_var = environment.get(env_key, default)
    if env_var != default:
        func = _default_type[type(default)]
        env_var = func(env_var)
    return env_var
