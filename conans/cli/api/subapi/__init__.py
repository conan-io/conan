import functools
import os
import sys

from conans.client.cache.cache import ClientCache
from conans.client.tools.env import environment_append
from conans.client.userio import init_colorama
from conans.util.tracer import log_command


def api_method(f):
    """Useful decorator to manage Conan API methods"""

    @functools.wraps(f)
    def wrapper(subapi, *args, **kwargs):
        quiet = kwargs.pop("quiet", False)
        try:  # getcwd can fail if Conan runs on an non-existing folder
            old_curdir = os.getcwd()
        except EnvironmentError:
            old_curdir = None

        if quiet:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            devnull = open(os.devnull, 'w')
            sys.stdout = devnull
            sys.stderr = devnull

        init_colorama(sys.stderr)

        try:
            # FIXME: Fix this hack if we want to keep the action recorder
            subapi_name = str(subapi.__class__.__name__).replace("API", "").lower()
            log_command("{}.{}".format(subapi_name, f.__name__), kwargs)
            # FIXME: Not pretty to instance here a ClientCache
            # FIXME: Remove this when everything is a subapi
            if hasattr(subapi, "conan_api"):
                config = ClientCache(subapi.conan_api.cache_folder).config
            else:
                config = ClientCache(subapi.cache_folder).config
            with environment_append(config.env_vars):
                return f(subapi, *args, **kwargs)
        finally:
            if old_curdir:
                os.chdir(old_curdir)
            if quiet:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
    return wrapper

