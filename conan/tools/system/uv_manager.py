import platform
import os
import shutil

from conan.tools.build import cmd_args_to_string
from conan.tools.env.environment import Environment
from conan.errors import ConanException


class UVEnv:

    def __init__(self, conanfile, py_version, folder=None, name=""):
        """
        :param conanfile: The current conanfile "self"
        :param folder: Optional folder, by default the "build_folder"
        :param name: Optional name for the virtualenv, by default "conan_uvenv"
        :param py_version: Optional python version for the virtualenv using UV
        """
        self._conanfile = conanfile
        # venv info
        self.env_name = f"conan_uvenv{f'_{name}' if name else ''}"
        self._base_env_dir = os.path.abspath(os.path.join(folder or conanfile.build_folder))
        self._env_dir = os.path.join(self._base_env_dir, self.env_name)
        self._uv_env_dir = os.path.join(self._base_env_dir, f"uv_{self.env_name}")
        self.bin_dir = os.path.join(self._env_dir,
                                    "Scripts" if platform.system() == "Windows" else "bin")
        self._create_uv_venv(py_version)

    @property
    def python(self):
        return self._get_env_python(self._env_dir)

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

    def _default_python_interpreter(self):
        python_interpreter = self._conanfile.conf.get("tools.system.pipenv:python_interpreter")
        if not python_interpreter:
            python = "python" if platform.system() == "Windows" else "python3"
            default_python = shutil.which(python)
            python_interpreter = os.path.realpath(default_python) if default_python else None
        if not python_interpreter:
            raise ConanException("UVEnv could not find a Python executable path. Please, install "
                                 "Python system-wide or set the "
                                 "'tools.system.pipenv:python_interpreter' "
                                 "conf to the full path of a Python executable")
        return python_interpreter

    def _create_uv_venv(self, py_version):
        _python = self._default_python_interpreter()
        _python_exe = self._get_env_python(self._uv_env_dir)
        try:
            self._conanfile.run(cmd_args_to_string(
                [_python, '-m', 'venv', self._uv_env_dir])
            )
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
                                 f"environment using UV and '{_python}': {e}")

    def run(self, args):
        return self._conanfile.run(cmd_args_to_string([self.python] + list(args)))

    def uvx(self, args):
        return self._conanfile.run(
            cmd_args_to_string([self._get_env_python(self._uv_env_dir), '-m', "uv", "tool", "run"] + list(args))
        )

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
