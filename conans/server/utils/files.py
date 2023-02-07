import os
import sys


def list_folder_subdirs(basedir, level):
    ret = []
    for root, dirs, _ in os.walk(basedir):
        rel_path = os.path.relpath(root, basedir)
        if rel_path == ".":
            continue
        dir_split = rel_path.split(os.sep)
        if len(dir_split) == level:
            ret.append("/".join(dir_split))
            dirs[:] = []  # Stop iterate subdirs
    return ret


def path_exists(path, basedir):
    """Case sensitive, for windows, optional
    basedir for skip caps check for tmp folders in testing for example (returned always
    in lowercase for some strange reason)"""
    exists = os.path.exists(path)
    if not exists or sys.platform == "linux2":
        return exists

    path = os.path.normpath(path)
    path = os.path.relpath(path, basedir)
    chunks = path.split(os.sep)
    tmp = basedir

    for chunk in chunks:
        if chunk and chunk not in os.listdir(tmp):
            return False
        tmp = os.path.normpath(tmp + os.sep + chunk)
    return True


def relative_dirs(path):
    """ Walks a dir and return a list with the relative paths """
    ret = []
    for dirpath, _, fnames in os.walk(path):
        for filename in fnames:
            tmp = os.path.join(dirpath, filename)
            tmp = tmp[len(path) + 1:]
            ret.append(tmp)
    return ret
