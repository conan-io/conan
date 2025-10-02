import platform
import os
import shutil
import sys

from conan.tools.build import cmd_args_to_string
from conan.tools.env.environment import Environment
from conan.errors import ConanException


class PipEnv:

    def __init__(self, conanfile, folder=None):
        self._conanfile = conanfile
        self.env_name = f"pip_venv_{self._conanfile.name}"
        self._env_dir = os.path.abspath(os.path.join(folder or self._conanfile.build_folder, self.env_name))
        self.bin_dir = os.path.join(self._env_dir, "Scripts" if platform.system() == "Windows" else "bin")
        self._python_exe = os.path.join(self.bin_dir, "python.exe" if platform.system() == "Windows" else "python")

    def generate(self):
        """
        Create a conan environment to use the python venv in the next steps of the conanfile.
        """
        env = Environment()
        env.prepend_path("PATH", self.bin_dir)
        env.vars(self._conanfile).save_script(self.env_name)

    def _create_venv(self):
        print("=" * 20)
        python_executable = None
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            if platform.system() == "Windows":
                candidate_names = ['python.exe', 'pythonw.exe']
            else:
                candidate_names = ['python', 'python3']

            for name in candidate_names:
                expected_path = os.path.join(sys._MEIPASS, name)
                print(expected_path)
                if os.path.exists(expected_path):
                    python_executable = expected_path
                    break
            if not python_executable:
                if platform.system() == "Windows":
                    system_py = shutil.which('python')
                else:
                    system_py = shutil.which('python3') or shutil.which('python')
                if system_py:
                    python_executable = system_py
        else:
            python_executable = sys.executable
        print("=" * 20)
        print(python_executable)
        print(getattr(sys, 'frozen', False))
        print(getattr(sys, '_MEIPASS', False))
        print("=" * 20)
        if not python_executable:
            raise ConanException("PipEnv could not find a Python executable path.")
        self._conanfile.run(cmd_args_to_string([python_executable, '-m', 'venv', self._env_dir]))

    def install(self, packages, pip_args=None):
        """
        Will try to install the list of pip packages passed as a parameter.

        :param packages: try to install the list of pip packages passed as a parameter.
        :param pip_args: additional argument list to be passed to the 'pip install' command,
                         for example: ['--no-cache-dir', '--index-url', 'https://my.pypi.org/simple'].
                         Defaults to ``None``.
        :return: the return code of the executed pip command.
        """

        self._create_venv()
        args = [self._python_exe, "-m", "pip", "install", "--disable-pip-version-check"]
        if pip_args:
            args += list(pip_args)
        args += list(packages)
        command = cmd_args_to_string(args)
        return self._conanfile.run(command)
