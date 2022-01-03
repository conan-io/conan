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
