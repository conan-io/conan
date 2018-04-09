"""
    Get variables from environment.
    Automatically handle types inferring datatype from default value.

    Usage:
        get_env('CONAN_SSL_ENABLED', False) => Will autotransform ENV CONAN_SSL_ENABLED to boolean

"""
import os


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
            return [var.strip() for var in env_var.split(",")]
    return env_var
