import platform
import os
import shutil
import sys

from conan.tools.build import cmd_args_to_string
from conan.tools.env.environment import Environment
from conan.errors import ConanException

from conan.api.output import ConanOutput

from conan.internal.util.files import rmdir


class PyEnv:

    def __init__(self, conanfile, folder=None, name="", py_version=None):
        """
        :param conanfile: The current conanfile ``self``
        :param folder: Optional folder, by default the ``build_folder``
        :param name: Optional name for the virtualenv, by default ``conan_pyenv``
        :param py_version: Optional python version to create the virtualenv using UV
        """
        if sys.version_info.minor < 8 and py_version:
            raise ConanException("'uv' needs Python >= 3.8. Please upgrade your Python interpreter"
                                 " or use 'PyEnv' without defining the 'py_version'.")

        self._conanfile = conanfile
        self._default_python = self._conanfile.conf.get("tools.system.pyenv:python_interpreter")
        # tools.system.pipenv deprecated warning message.
        if not self._default_python and self._conanfile.conf.get("tools.system.pipenv:python_interpreter"):
            self._default_python = self._conanfile.conf.get("tools.system.pipenv:python_interpreter")
            ConanOutput().warning("'tools.system.pipenv:python_interpreter' "
                                  "is deprecated, use 'tools.system.pyenv:python_interpreter'",
                                  warn_tag="deprecated")

        if not self._default_python:
            python = "python" if platform.system() == "Windows" else "python3"
            default_python = shutil.which(python)
            self._default_python = os.path.realpath(default_python) if default_python else None
        if not self._default_python:
            raise ConanException("Conan could not find a Python executable path. Please, install "
                                 "Python system-wide or set the "
                                 "'tools.system.pyenv:python_interpreter' "
                                 "conf to the full path of a Python executable")
        self._env_name = f"conan_pyenv{f'_{name}' if name else ''}"
        if py_version:
            self._env_name += f'_{py_version.replace(".", "_")}'
        base_env_dir = os.path.abspath(folder or conanfile.build_folder)
        self._env_dir = os.path.join(base_env_dir, self._env_name)
        if not os.path.exists(self._env_dir):
            if py_version:
                self._create_uv_venv(base_env_dir, py_version)
            else:
                self._create_venv()

    @property
    def env_dir(self):
        """Root directory of the virtual environment."""
        return self._env_dir.replace("\\", "/")

    @property
    def env_exe(self):
        """Path to the Python executable inside the virtual environment."""
        return self._get_env_python(self._env_dir).replace("\\", "/")

    @property
    def bin_path(self):
        """Path to the bin or Scripts directory inside the virtual environment."""
        bins = "Scripts" if platform.system() == "Windows" else "bin"
        return os.path.join(self._env_dir, bins).replace("\\", "/")

    @staticmethod
    def _get_env_python(env_dir):
        _env_bin_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
        return os.path.join(_env_bin_dir, "python.exe" if platform.system() == "Windows" else "python")

    def generate(self):
        """
        Create a conan environment to use the python venv in the next steps of the conanfile.
        """
        env = Environment()
        env.prepend_path("PATH", self.bin_path)
        env.vars(self._conanfile).save_script(self._env_name)

    def run(self, args):
        return self._conanfile.run(cmd_args_to_string([self.env_exe] + list(args)))

    def install(self, packages, pip_args=None):
        """
        Will try to install the list of pip packages passed as a parameter.

        :param packages: try to install the list of pip packages passed as a parameter.
        :param pip_args: additional argument list to be passed to the 'pip install' command,
                         e.g.: ['--no-cache-dir', '--index-url', 'https://my.pypi.org/simple'].
                         Defaults to ``None``.
        :return: the return code of the executed pip command.
        """
        args = [self.env_exe, "-m", "pip", "install", "--disable-pip-version-check"]
        if pip_args:
            args.extend(pip_args)
        args += [f'"{p}"' for p in packages]
        command = " ".join(args)
        return self._conanfile.run(command)

    def _create_venv(self):
        try:
            self._conanfile.run(cmd_args_to_string([self._default_python, '-m', 'venv',
                                                    self._env_dir]))
        except ConanException as e:
            raise ConanException(f"PyEnv could not create a Python virtual "
                                 f"environment using '{self._default_python}': {e}")

    def _create_uv_venv(self, base_env_dir, py_version):
        uv_env_dir = None
        try:
            uv_path = shutil.which("uv")
            if uv_path:
                uv_cmd = [uv_path]
            else:
                uv_env_dir = os.path.join(base_env_dir, f"uv_{self._env_name}")
                self._conanfile.run(cmd_args_to_string(
                    [self._default_python, '-m', 'venv', uv_env_dir])
                )

                python_exe = self._get_env_python(uv_env_dir)
                self._conanfile.run(cmd_args_to_string(
                    [python_exe, "-m", "pip", "install", "--disable-pip-version-check", "uv"])
                )
                uv_cmd = [python_exe, "-m", "uv"]

            self._conanfile.run(cmd_args_to_string(uv_cmd + ['venv', '--seed', '--python', py_version, self._env_dir]))
            self._conanfile.output.info(f"Virtual environment for Python "
                                        f"{py_version} created successfully using UV.")
        except Exception as e:
            raise ConanException(f"PyEnv could not create a Python {py_version} virtual "
                                 f"environment using UV and '{self._default_python}': {e}")
        finally:
            if uv_env_dir:
                rmdir(uv_env_dir)


class PipEnv(PyEnv):
    def __init__(self, conanfile, folder=None, name="", py_version=None):
        super().__init__(conanfile, folder, name, py_version)
        ConanOutput().warning("'PipEnv()' is deprecated, use 'PyEnv()'", warn_tag="deprecated")
