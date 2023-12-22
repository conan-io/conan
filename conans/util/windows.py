import os


def conan_expand_user(path):
    """ wrapper to the original expanduser function, to workaround python returning
    verbatim %USERPROFILE% when some other app (git for windows) sets HOME envvar
    """
    path = str(path)
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
