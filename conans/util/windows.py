import os


def conan_expand_user(path):
    """ wrapper to the original expanduser function, to workaround python returning
    verbatim %USERPROFILE% when some other app (git for windows) sets HOME envvar
    """
    path = str(path)
    if path[:1] != '~':
        return path
    # In win these variables should exist and point to user directory, which
    # must exist.
    try:
        home = os.environ.get("HOME")
        # Problematic cases of wrong HOME variable
        # - HOME = %USERPROFILE% verbatim, as messed by some other tools
        # - MSYS console, that defines a different user home in /c/mingw/msys/users/xxx
        # In these cases, it is safe to remove it and rely on USERPROFILE directly
        if home and (not os.path.exists(home) or
                     (os.getenv("MSYSTEM") and os.getenv("USERPROFILE"))):
            del os.environ["HOME"]
        # Problematic cases of existing ORIGINAL_PATH variable
        # - msys /etc/profile, for MSYS2_PATH_TYPE=inherit mode:
        #   - If ORIGINAL_PATH is unset, then assign ORIGINAL_PATH=PATH
        #   - Set PATH=some msys paths plus ORIGINAL_PATH
        # - To ensure we keep PATH intact, we must ensure ORIGINAL_PATH is unset
        # - A user running conan from an msys console typically has ORIGINAL_PATH already set
        # - To ensure conan's build paths are correct, ORIGINAL_PATH must be unset
        if os.getenv("ORIGINAL_PATH"):
            del os.environ["ORIGINAL_PATH"]
        result = os.path.expanduser(path)
    finally:
        if home is not None:
            os.environ["HOME"] = home
    return result
