import os
import subprocess

from conans.util.files import load, mkdir, save, rmdir
import tempfile


CONAN_LINK = ".conan_link"


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


def _give_full_control_current_user(folder):
    """
    Gives to the current user full control in folder. In cygwin and msys2 if current user doesn't
    have full control there will be access problems for new files under folder. Problem only observed
    when cygwin/msys2 work on mounted NTFS drive
    :param folder:
    """
    try:
        cmd = 'cacls %s /E /G "%s\\%s":F' % (folder, os.environ['USERDOMAIN'], os.environ['USERNAME'])
        subprocess.check_output(cmd, stderr=subprocess.STDOUT)  # Ignoring any returned output, make command quiet
    except subprocess.CalledProcessError as e:
        if "NTFS" in str(e.output):
            # cacls only works for NTFS drives. If folder is living in non NTFS drive it will return:
            # """The Cacls command can be run only on disk drives that use the NTFS file system."""
            return
        raise


def path_shortener(path, short_paths):
    """ short_paths is 4-state:
    False: Never shorten the path
    True: Always shorten the path, create link if not existing
    None: Use shorten path only if already exists, not create
    """
    if short_paths is False or os.getenv("CONAN_USER_HOME_SHORT") == "None":
        return path
    link = os.path.join(path, CONAN_LINK)
    if os.path.exists(link):
        return load(link)
    elif short_paths is None:
        return path

    short_home = os.getenv("CONAN_USER_HOME_SHORT")
    if not short_home:
        drive = os.path.splitdrive(path)[0]
        short_home = drive + "/.conan"
    mkdir(short_home)

    # Workaround for folders in NTFS drives
    _give_full_control_current_user(short_home)

    redirect = tempfile.mkdtemp(dir=short_home, prefix="")
    # This "1" is the way to have a non-existing directory, so commands like
    # shutil.copytree() to it, works. It can be removed without compromising the
    # temp folder generator and conan-links consistency
    redirect = os.path.join(redirect, "1")
    save(link, redirect)
    return redirect


def ignore_long_path_files(src_folder, build_folder, output):
    def _filter(src, files):
        filtered_files = []
        for the_file in files:
            source_path = os.path.join(src, the_file)
            # Without storage path, just relative
            rel_path = os.path.relpath(source_path, src_folder)
            dest_path = os.path.normpath(os.path.join(build_folder, rel_path))
            # it is NOT that "/" is counted as "\\" so it counts double
            # seems a bug in python, overflows paths near the limit of 260,
            if len(dest_path) >= 249:
                filtered_files.append(the_file)
                output.warn("Filename too long, file excluded: %s" % dest_path)
        return filtered_files
    return _filter


def rm_conandir(path):
    """removal of a directory that might contain a link to a short path"""
    link = os.path.join(path, CONAN_LINK)
    if os.path.exists(link):
        short_path = load(link)
        rmdir(os.path.dirname(short_path))
    rmdir(path)
