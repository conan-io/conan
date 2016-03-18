"""
    Get variables from environment.
    Automatically handle types inferring datatype from default value.

    Usage:
        get_env('CONAN_SSL_ENABLED', False) => Will autotransform ENV CONAN_SSL_ENABLED to boolean

"""
import os


def get_env(env_key, default=None, environment=os.environ):
    '''Get the env variable associated with env_key'''
    _default_type = {str: lambda x: x,
                     int: lambda x: int(x),
                     float: lambda x: float(x),
                     list: lambda x: x.split(","),
                     bool: lambda x: x == '1'}

    env_var = environment.get(env_key, default)
    if env_var != default:
        if isinstance(default, str):
            return env_var
        elif isinstance(default, int):
            return int(env_var)
        elif isinstance(default, float):
            return float(env_var)
        elif isinstance(default, list):
            return env_var.split(",")
        elif isinstance(default, bool):
            return env_var == "1"
    
    return env_var
