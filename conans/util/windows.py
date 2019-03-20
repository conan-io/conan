import os
import subprocess
import tempfile

from conans.util.env_reader import get_env
from conans.util.files import load, mkdir, rmdir, save
from conans.util.log import logger
from conans.util.sha import sha256

CONAN_LINK = ".conan_link"
CONAN_REAL_PATH = "real_path.txt"


def conan_expand_user(path):
    """ wrapper to the original expanduser function, to workaround python returning
    verbatim %USERPROFILE% when some other app (git for windows) sets HOME envvar
    """
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


def path_shortener(path, short_paths):
    """ short_paths is 4-state:
    False: Never shorten the path
    True: Always shorten the path, create link if not existing
    None: Use shorten path only if already exists, not create
    """
    use_always_short_paths = get_env("CONAN_USE_ALWAYS_SHORT_PATHS", False)
    short_paths = use_always_short_paths or short_paths

    if short_paths is False or os.getenv("CONAN_USER_HOME_SHORT") == "None":
        return path
    link = os.path.join(path, CONAN_LINK)
    if os.path.exists(link):
        return load(link)
    elif short_paths is None:
        return path

    if os.path.exists(path):
        rmdir(path)

    short_home = os.getenv("CONAN_USER_HOME_SHORT")
    if not short_home:
        drive = os.path.splitdrive(path)[0]
        short_home = os.path.join(drive, os.sep, ".conan")
    mkdir(short_home)

    # Workaround for short_home living in NTFS file systems. Give full control permission
    # to current user to avoid
    # access problems in cygwin/msys2 windows subsystems when using short_home folder
    try:
        userdomain, username = os.getenv("USERDOMAIN"), os.environ["USERNAME"]
        domainname = "%s\%s" % (userdomain, username) if userdomain else username
        cmd = r'cacls %s /E /G "%s":F' % (short_home, domainname)
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)  # Ignoring any returned output, quiet
    except subprocess.CalledProcessError:
        # cmd can fail if trying to set ACL in non NTFS drives, ignoring it.
        pass

    redirect = hashed_redirect(short_home, path)
    if not redirect:
        logger.warning("Failed to create a deterministic short path in %s", short_home)
        redirect = tempfile.mkdtemp(dir=short_home, prefix="")

    # Save the full path of the local cache directory where the redirect is from.
    # This file is for debugging purposes and not used by Conan.
    save(os.path.join(redirect, CONAN_REAL_PATH), path)

    # This "1" is the way to have a non-existing directory, so commands like
    # shutil.copytree() to it, works. It can be removed without compromising the
    # temp folder generator and conan-links consistency
    redirect = os.path.join(redirect, "1")
    save(link, redirect)
    return redirect


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
