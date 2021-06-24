import os
import subprocess
import tempfile

from conans.client.tools.oss import OSInfo
from conans.errors import ConanException
from conans.util.env_reader import get_env
from conans.util.files import decode_text
from conans.util.files import load, mkdir, rmdir, save
from conans.util.log import logger
from conans.util.sha import sha256

CONAN_LINK = ".conan_link"
CONAN_REAL_PATH = "real_path.txt"


def conan_expand_user(path):
    """ wrapper to the original expanduser function, to workaround python returning
    verbatim %USERPROFILE% when some other app (git for windows) sets HOME envvar
    """
    if path[:1] != '~':
        return path
    # In win these variables should exist and point to user directory, which
    # must exist. Using context to avoid permanent modification of os.environ
    old_env = dict(os.environ)
    try:
        home = os.environ.get("HOME")
        # Problematic cases of wrong HOME variable
        # - HOME = %USERPROFILE% verbatim, as messed by some other tools
        # - MSYS console, that defines a different user home in /c/mingw/msys/users/xxx
        # In these cases, it is safe to remove it and rely on USERPROFILE directly
        if home and (not os.path.exists(home) or
                     (os.getenv("MSYSTEM") and os.getenv("USERPROFILE"))):
            del os.environ["HOME"]
        result = os.path.expanduser(path)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    return result


def rm_conandir(path):
    """removal of a directory that might contain a link to a short path"""
    link = os.path.join(path, CONAN_LINK)
    if os.path.exists(link):
        short_path = load(link)
        rmdir(os.path.dirname(short_path))
    rmdir(path)


def hashed_redirect(base, path, min_length=6, attempts=10):
    max_length = min_length + attempts

    full_hash = sha256(path.encode())
    assert len(full_hash) > max_length

    for length in range(min_length, max_length):
        redirect = os.path.join(base, full_hash[:length])
        if not os.path.exists(redirect):
            return redirect
    else:
        return None
