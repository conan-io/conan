import functools
import os

from conans.util.tracer import log_conan_api_call


def api_method(f):
    """Useful decorator to manage Conan API methods"""

    @functools.wraps(f)
    def wrapper(subapi, *args, **kwargs):
        try:  # getcwd can fail if Conan runs on an non-existing folder
            old_curdir = os.getcwd()
        except EnvironmentError:
            old_curdir = None

        try:
            # FIXME: Fix this hack if we want to keep the action recorder
            subapi_name = str(subapi.__class__.__name__).replace("API", "").lower()
            log_conan_api_call("{}.{}".format(subapi_name, f.__name__), kwargs)
            return f(subapi, *args, **kwargs)
        finally:
            if old_curdir:
                os.chdir(old_curdir)

    return wrapper
