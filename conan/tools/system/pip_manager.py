import platform
import os
import shutil

from conan.tools.build import cmd_args_to_string
from conan.tools.env.environment import Environment
from conan.errors import ConanException


class PythonVirtualEnv:

    def __init__(self, conanfile, folder=None, name=""):
        """
        :param conanfile: The current conanfile "self"
        :param folder: Optional folder, by default the "build_folder"
        :param name: Optional name for the virtualenv, by default "conan_pipenv"
        """
        self._conanfile = conanfile
        self.env_name = f"conan_pipenv{f'_{name}' if name else ''}"
        self._env_dir = os.path.abspath(os.path.join(folder or conanfile.build_folder,
                                                     self.env_name))
        bins = "Scripts" if platform.system() == "Windows" else "bin"
        self.bin_dir = os.path.join(self._env_dir, bins)
        pyexe = "python.exe" if platform.system() == "Windows" else "python"
        self._python_exe = os.path.join(self.bin_dir, pyexe)

    @property
    def python(self):
        return self._get_env_python(self._env_dir)

    @property
    def _default_python(self):
        _config_python = self._conanfile.conf.get("tools.system.pipenv:python_interpreter")
        python = "python" if platform.system() == "Windows" else "python3"
        default_python = shutil.which(python)
        _system_python = os.path.realpath(default_python) if default_python else None
        _python = _config_python or _system_python
        if _python:
            return _python
        else:
            raise ConanException("Conan could not find a Python executable path. Please, install "
                                 "Python system-wide or set the "
                                 "'tools.system.pipenv:python_interpreter' "
                                 "conf to the full path of a Python executable")

    @staticmethod
    def _get_env_python(env_dir):
        _env_bin_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
        return os.path.join(_env_bin_dir, "python.exe" if platform.system() == "Windows" else "python")

    def generate(self):
        """
        Create a conan environment to use the python venv in the next steps of the conanfile.
        """
        env = Environment()
        env.prepend_path("PATH", self.bin_dir)
        env.vars(self._conanfile).save_script(self.env_name)

    def run(self, args):
        return self._conanfile.run(cmd_args_to_string([self.python] + list(args)))

    def install(self, packages, pip_args=None):
        """
        Will try to install the list of pip packages passed as a parameter.

        :param packages: try to install the list of pip packages passed as a parameter.
        :param pip_args: additional argument list to be passed to the 'pip install' command,
                         e.g.: ['--no-cache-dir', '--index-url', 'https://my.pypi.org/simple'].
                         Defaults to ``None``.
        :return: the return code of the executed pip command.
        """
        args = ["-m", "pip", "install", "--disable-pip-version-check"]
        if pip_args:
            args += list(pip_args)
        args += list(packages)
        return self.run(args)


class PipEnv(PythonVirtualEnv):

    def __init__(self, conanfile, folder=None, name=""):
        """
        :param conanfile: The current conanfile "self"
        :param folder: Optional folder, by default the "build_folder"
        :param name: Optional name for the virtualenv, by default "conan_pipenv"
        """
        super().__init__(conanfile, folder, name)
        self._create_venv()

    def _create_venv(self):
        try:
            self._conanfile.run(cmd_args_to_string([self._default_python, '-m', 'venv',
                                                    self._env_dir]))
        except ConanException as e:
            raise ConanException(f"PipEnv could not create a Python virtual "
                                 f"environment using '{self._default_python}': {e}")


class UVEnv(PythonVirtualEnv):

    def __init__(self, conanfile, py_version, folder=None, name=""):
        """
        :param conanfile: The current conanfile "self"
        :param folder: Optional folder, by default the "build_folder"
        :param name: Optional name for the virtualenv, by default "conan_uvenv"
        :param py_version: Optional python version for the virtualenv using UV
        """
        super().__init__(conanfile, folder, name)
        self._base_env_dir = os.path.abspath(os.path.join(folder or conanfile.build_folder))
        self._uv_env_dir = os.path.join(self._base_env_dir, f"uv_{self.env_name}")
        self._create_uv_venv(py_version)

    def _create_uv_venv(self, py_version):
        try:
            self._conanfile.run(cmd_args_to_string(
                [self._default_python, '-m', 'venv', self._uv_env_dir])
            )
            _python_exe = self._get_env_python(self._uv_env_dir)
            self._conanfile.run(cmd_args_to_string(
                [_python_exe, "-m", "pip", "install", "--disable-pip-version-check", "uv"])
            )
            self._conanfile.run(cmd_args_to_string(
                [_python_exe, '-m', 'uv', 'venv', '--seed', '--python', py_version, self._env_dir])
            )
            self._conanfile.output.info(f"Virtual environment for Python "
                                        f"{py_version} created successfully using UV.")
        except Exception as e:
            raise ConanException(f"UVEnv could not create a Python {py_version} virtual "
                                 f"environment using UV and '{self._default_python}': {e}")

    def uvx(self, args):
        return self._conanfile.run(
            cmd_args_to_string([self._get_env_python(self._uv_env_dir), '-m', "uv", "tool", "run"] + list(args))
        )
