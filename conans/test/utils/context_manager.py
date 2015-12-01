import os
import glob
import copy


class CustomEnvPath():
    '''
    Class to create a custom environment with 3 paramenters:
        -paths_to_add: list with all the paths that you need in the environments
        -paths_to_remove: list with all the paths that you need to remove from the environment
        -cmds_to_remove: list of commands that you need to remove from paths.
         This class looks for its path and remove it from paths.
    '''
    def __init__(self, paths_to_add=None, paths_to_remove=None,
                 var_to_add=None, var_to_remove=None, cmds_to_remove=None):
        self._original_env = copy.deepcopy(os.environ)
        self._paths_to_add = paths_to_add
        self._paths_to_remove = paths_to_remove or []
        self._var_to_add = var_to_add
        self._var_to_remove = var_to_remove or []
        self._cmds_to_remove = cmds_to_remove

    def __enter__(self):
        if self._var_to_add:
            for name, value in self._var_to_add:
                os.environ[name] = value
        if self._var_to_remove:
            for name in self._var_to_add:
                os.environ[name] = None
        if self._paths_to_add:
            os.environ['PATH'] = "%s%s%s" % (os.environ['PATH'],
                                             os.pathsep,
                                             os.pathsep.join(self._paths_to_add))

        if self._cmds_to_remove:
            for cmd in self._cmds_to_remove:
                self._paths_to_remove.extend(which(cmd))

        if self._paths_to_remove:
            env = os.environ['PATH'].split(os.pathsep)
            os.environ['PATH'] = os.pathsep.join([p for p in env if p not in self._paths_to_remove])

    def __exit__(self, _type, value, traceback):
        os.environ = self._original_env


def which(program):
    path_found = []

    def is_exe(fpath):
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            path_found.append(fpath)
    else:
        _, ext = os.path.splitext(program)
        if ext:
            file_to_find = program
        else:
            file_to_find = "%s.*" % program
        for path in os.environ["PATH"].split(os.pathsep):
            for _file in glob.glob(os.path.join(path, file_to_find)):
                if is_exe(os.path.join(path, _file)):
                    path_found.append(path)

    return path_found
