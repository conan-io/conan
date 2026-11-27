import os


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


def relative_dirs(path):
    """ Walks a dir and return a list with the relative paths """
    ret = []
    for dirpath, _, fnames in os.walk(path):
        for filename in fnames:
            tmp = os.path.join(dirpath, filename)
            tmp = tmp[len(path) + 1:]
            ret.append(tmp)
    return ret
