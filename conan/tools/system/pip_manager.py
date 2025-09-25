import venv
import platform
import os

from conan.errors import ConanException
from conan.tools.build import cmd_args_to_string
from conan.tools.env.environment import Environment


class PipEnv:

    def __init__(self, conanfile, folder=None):
        self._conanfile = conanfile
        self.env_name = f"pip_venv_{self._conanfile.name}"
        self._env_dir = os.path.abspath(os.path.join(folder or self._conanfile.build_folder, self.env_name))
        self.bin_dir = os.path.join(self._env_dir, "Scripts" if platform.system() == "Windows" else "bin")
        self._python_exe = os.path.join(self.bin_dir, "python.exe" if platform.system() == "Windows" else "python")

    def generate(self):
        """
        Will try to create a conan virtual env to use the python venv in the next steps.
        We need to use this method in the generate step or earlier in order to use this environment in the following steps.
        """
        env = Environment()
        env.prepend_path("PATH", self.bin_dir)
        env.vars(self._conanfile).save_script(self.env_name)

    def install(self, packages, pip_args=None):
        """
        Will try to install the list of pip packages passed as a parameter.

        :param packages: try to install the list of pip packages passed as a parameter.
        :param pip_args: additional argument list to be passed to the 'pip install' command,
                         for example: ['--no-cache-dir', '--index-url', 'https://my.pypi.org/simple'].
                         Defaults to ``None``.

        :return: the return code of the executed pip command.
        """

        venv.EnvBuilder(clear=True, with_pip=True).create(self._env_dir)
        pip_args = list(pip_args) if pip_args else []
        args = [self._python_exe, "-m", "pip", "install", "--disable-pip-version-check"] + pip_args
        args += list(packages)
        command = cmd_args_to_string(args)

        ret = self._conanfile.run(command, ignore_errors=True, quiet=True)
        if ret == 0:
            return ret
        raise ConanException("Command '%s' failed" % command)
