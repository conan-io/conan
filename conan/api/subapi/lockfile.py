import os

from conan.api.output import ConanOutput
from conan.cli import make_abs_path
from conans.client.graph.graph import Overrides
from conans.errors import ConanException
from conans.model.graph_lock import Lockfile, LOCKFILE


class LockfileAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @staticmethod
    def get_lockfile(lockfile=None, conanfile_path=None, cwd=None, partial=False, overrides=None):
        """ obtain a lockfile, following this logic:
        - If lockfile is explicitly defined, it would be either absolute or relative to cwd and
          the lockfile file must exist. If lockfile="" (empty string) the default "conan.lock"
          lockfile will not be automatically used even if it is present.
        - If lockfile is not defined, it will still look for a default conan.lock:
           - if conanfile_path is defined, it will be besides it
           - if conanfile_path is not defined, the default conan.lock should be in cwd
           - if the default conan.lock cannot be found, it is not an error

        :param partial: If the obtained lockfile will allow partial resolving
        :param cwd: the current working dir, if None, os.getcwd() will be used
        :param conanfile_path: The full path to the conanfile, if existing
        :param lockfile: the name of the lockfile file
        :param overrides: Dictionary of overrides {overriden: [new_ref1, new_ref2]}
        """
        if lockfile == "":
            # Allow a way with ``--lockfile=""`` to optout automatic usage of conan.lock
            return

        cwd = cwd or os.getcwd()
        if lockfile is None:  # Look for a default "conan.lock"
            # if path is defined, take it as reference
            base_path = os.path.dirname(conanfile_path) if conanfile_path else cwd
            lockfile_path = make_abs_path(LOCKFILE, base_path)
            if not os.path.isfile(lockfile_path):
                if overrides:
                    raise ConanException("Cannot define overrides without a lockfile")
                return
        else:  # explicit lockfile given
            lockfile_path = make_abs_path(lockfile, cwd)
            if not os.path.isfile(lockfile_path):
                raise ConanException("Lockfile doesn't exist: {}".format(lockfile_path))

        graph_lock = Lockfile.load(lockfile_path)
        graph_lock.partial = partial

        if overrides:
            graph_lock._overrides = Overrides.deserialize(overrides)
        ConanOutput().info("Using lockfile: '{}'".format(lockfile_path))
        return graph_lock

    def update_lockfile_export(self, lockfile, conanfile, ref, is_build_require=False):
        # The package_type is not fully processed at export
        is_python_require = conanfile.package_type == "python-require"
        is_require = not is_python_require and not is_build_require
        if hasattr(conanfile, "python_requires"):
            python_requires = conanfile.python_requires.all_refs()
        else:
            python_requires = []
        python_requires = python_requires + ([ref] if is_python_require else [])
        lockfile = self.add_lockfile(lockfile,
                                     requires=[ref] if is_require else None,
                                     python_requires=python_requires,
                                     build_requires=[ref] if is_build_require else None)
        return lockfile

    @staticmethod
    def update_lockfile(lockfile, graph, lock_packages=False, clean=False):
        if lockfile is None or clean:
            lockfile = Lockfile(graph, lock_packages)
        else:
            lockfile.update_lock(graph, lock_packages)
        return lockfile

    @staticmethod
    def add_lockfile(lockfile=None, requires=None, build_requires=None, python_requires=None,
                     config_requires=None):
        if lockfile is None:
            lockfile = Lockfile()  # create a new lockfile
            lockfile.partial = True

        lockfile.add(requires=requires, build_requires=build_requires,
                     python_requires=python_requires, config_requires=config_requires)
        return lockfile

    @staticmethod
    def remove_lockfile(lockfile, requires=None, build_requires=None, python_requires=None,
                        config_requires=None):
        lockfile.remove(requires=requires, build_requires=build_requires,
                        python_requires=python_requires, config_requires=config_requires)
        return lockfile

    @staticmethod
    def save_lockfile(lockfile, lockfile_out, path=None):
        if lockfile_out is not None:
            lockfile_out = make_abs_path(lockfile_out, path)
            lockfile.save(lockfile_out)
            ConanOutput().info(f"Generated lockfile: {lockfile_out}")
