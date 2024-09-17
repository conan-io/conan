from pathlib import Path
from contextlib import contextmanager
from conans import tools

import os
import sys
import itertools
import operator


# mostly like shutil.which, but allows searching for alternate filenames,
# and never falls back to %PATH% or curdir
def _which(files, paths, access=os.F_OK | os.X_OK):
    if isinstance(files, str):
        files = [files]
    if sys.platform == "win32":
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)

        def expand_pathext(cmd):
            if any(cmd.lower().endswith(ext.lower()) for ext in pathext):
                yield cmd  # already has an extension, so check only that one
            else:
                yield from (cmd + ext for ext in pathext)  # check all possibilities

        files = [x for cmd in files for x in expand_pathext(cmd)]

        # Windows filesystems are (usually) case-insensitive, so match might be spelled differently than the searched name
        # And in particular, the extensions from PATHEXT are usually uppercase, and yet the real file seldom is.
        # Using pathlib.resolve() for now because os.path.realpath() was a no-op on win32
        # until nt symlink support landed in python 3.9 (based on GetFinalPathNameByHandleW)
        # https://github.com/python/cpython/commit/75e064962ee0e31ec19a8081e9d9cc957baf6415
        #
        # realname() canonicalizes *only* the searched-for filename, but keeps the caller-provided path verbatim:
        # they might have been short paths, or via some symlink, and that's fine

        def realname(file):
            path = Path(file)
            realname = path.resolve(strict=True).name
            return str(path.with_name(realname))

    else:

        def realname(path):
            return path  # no-op

    for path in paths:
        for file in files:
            filepath = os.path.join(path, file)
            if (
                os.path.exists(filepath)
                and os.access(filepath, access)
                and not os.path.isdir(filepath)
            ):  # is executable
                return realname(filepath)
    return None


def _default_python():
    base_exec_prefix = sys.base_exec_prefix

    if hasattr(
        sys, "real_prefix"
    ):  # in a virtualenv, which sets this instead of base_exec_prefix like venv
        base_exec_prefix = getattr(sys, "real_prefix")

    if sys.exec_prefix != base_exec_prefix:  # alread running in a venv
        # we want to create the new virtualenv off the base python installation,
        # rather than create a grandchild (child of of the current venv)
        names = [os.path.basename(sys.executable), "python3", "python"]

        prefixes = [base_exec_prefix]

        suffixes = ["bin", "Scripts"]
        exec_prefix_suffix = os.path.relpath(
            os.path.dirname(sys.executable), sys.exec_prefix
        )  # e.g. bin or Scripts
        if exec_prefix_suffix and exec_prefix_suffix != ".":
            suffixes.insert(0, exec_prefix_suffix)

        def add_suffix(prefix, suffixes):
            yield prefix
            yield from (os.path.join(prefix, suffix) for suffix in suffixes)

        dirs = [x for prefix in prefixes for x in add_suffix(prefix, suffixes)]
        return _which(names, dirs)
    else:
        return sys.executable


# build helper for making and managing python virtual environments
class PythonVirtualEnv:
    def __init__(self, conanfile, python=_default_python(), env_folder=None):
        self._conanfile = conanfile
        self.base_python = python
        self.env_folder = env_folder

    # symlink logic borrowed from python -m venv
    # See venv.main() in /Lib/venv/__init__
    def create(self, folder, *, clear=True, symlinks=(os.name != "nt"), with_pip=True):
        self.env_folder = folder

        self._conanfile.output.info(
            "creating venv at %s based on %s"
            % (self.env_folder, self.base_python or "<conanfile>")
        )

        if self.base_python:
            # another alternative (if we ever wanted to support more customization) would be to launch
            # a `python -` subprocess and feed it the script text `import venv venv.EnvBuilder() ...` on stdin
            venv_options = ["--symlinks" if symlinks else "--copies"]
            if clear:
                venv_options.append("--clear")
            if not with_pip:
                venv_options.append("--without-pip")
            with tools.environment_append({"__PYVENV_LAUNCHER__": None}):
                self._conanfile.run(
                    tools.args_to_string(
                        [self.base_python, "-mvenv", *venv_options, self.env_folder]
                    )
                )
        else:
            # fallback to using the python this script is running in
            # (risks the new venv having an inadvertant dependency if conan itself is virtualized somehow, but it will *work*)
            import venv

            builder = venv.EnvBuilder(clear=clear, symlinks=symlinks, with_pip=with_pip)
            builder.create(self.env_folder)

    def entry_points(self, package=None):
        import importlib.metadata  # Python 3.8 or greater

        entry_points = itertools.chain.from_iterable(
            dist.entry_points
            for dist in importlib.metadata.distributions(
                name=package, path=self.lib_paths
            )
        )

        by_group = operator.attrgetter("group")
        ordered = sorted(entry_points, key=by_group)
        grouped = itertools.groupby(ordered, by_group)

        return {
            group: [x.name for x in entry_points] for group, entry_points in grouped
        }

    def setup_entry_points(self, package, folder, silent=False):
        # create target folder
        try:
            os.makedirs(folder)
        except Exception:
            pass

        def copy_executable(name, target_folder, type):
            import shutil

            # locate script in venv
            try:
                path = self.which(name, required=True)
            except FileNotFoundError as e:
                # avoid FileNotFound if the no launcher script for this name was found, or
                self._conanfile.output.warn(
                    "pyvenv.setup_entry_points: FileNotFoundError: %s" % e
                )
                return

            root, ext = os.path.splitext(path)

            try:
                # copy venv script to target folder
                shutil.copy2(path, target_folder)

                # copy entry point script
                # if it exists
                if type == "gui":
                    ext = "-script.pyw"
                else:
                    ext = "-script.py"

                entry_point_script = root + ext

                if os.path.isfile(entry_point_script):
                    shutil.copy2(entry_point_script, target_folder)
            except shutil.SameFileError:
                # SameFileError if the launcher script is *already* in the target_folder
                # e.g. on posix systems the venv scripts are already in bin/
                if not silent:
                    self._conanfile.output.info(
                        f"pyvenv.setup_entry_points: command '{name}' already found in '{folder}'. Other entry_points may also be unintentionally visible."
                    )

        entry_points = self.entry_points(package)
        for name in entry_points.get("console_scripts", []):
            self._conanfile.output.info(f"Adding entry point for {name}")
            copy_executable(name, folder, type="console")
        for name in entry_points.get("gui_scripts", []):
            self._conanfile.output.info(f"Adding entry point for {name}")
            copy_executable(name, folder, type="gui")

    @property
    def bin_paths(self):
        # this should be the same logic as as
        # context.bin_name = ... in venv.ensure_directories
        if sys.platform == "win32":
            binname = "Scripts"
        else:
            binname = "bin"
        bindirs = [binname]
        return [os.path.join(self.env_folder, x) for x in bindirs]

    @property
    def lib_paths(self):
        # this should be the same logic as as
        # libpath = ... in venv.ensure_directories
        if sys.platform == "win32":
            libpath = os.path.join(self.env_folder, "Lib", "site-packages")
        else:
            libpath = os.path.join(
                self.env_folder,
                "lib",
                "python%d.%d" % sys.version_info[:2],
                "site-packages",
            )
        return [libpath]

    # return the path to a command within the venv, None if only found outside
    def which(self, command, required=False, **kwargs):
        found = _which(command, self.bin_paths, **kwargs)
        if found:
            return found
        elif required:
            raise FileNotFoundError(
                "command %s not in venv bin_paths %s"
                % (command, os.pathsep.join(self.bin_paths))
            )
        else:
            return None

    # convenience wrappers for python/pip since they are so commonly needed
    @property
    def python(self):
        return self.which("python", required=True)

    @property
    def pip(self):
        return self.which("pip", required=True)

    # environment variables like the usual venv `activate` script, i.e.
    # with tools.environment_append(venv.env):
    #     ...
    @property
    def env(self):
        return {
            "__PYVENV_LAUNCHER__": None,  # this might already be set if conan was launched through a venv
            "PYTHONHOME": None,
            "VIRTUAL_ENV": self.env_folder,
            "PATH": self.bin_paths,
        }

    # Setup environment and add site_packages of this this venv to sys.path
    # (importing from the venv only works if it contains python modules compatible
    #  with conan's python interrpreter as well as the venv one
    # But they're generally the same per _default_python(), so this will let you try
    # with venv.activate():
    #     ...
    @contextmanager
    def activate(self):
        old_path = sys.path[:]
        sys.path.extend(self.lib_paths)
        with tools.environment_append(self.env):
            yield
        sys.path = old_path
