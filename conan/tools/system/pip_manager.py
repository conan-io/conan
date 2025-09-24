import venv
import platform
import os

from conan.errors import ConanException
from conan.tools.env.environment import Environment


class PipEnv:
    accepted_install_codes = [0]
    accepted_check_codes = [0, 1]

    def __init__(self, conanfile, folder=None):
        self._conanfile = conanfile
        self.env_name = f"pip_venv_{self._conanfile.name}"
        self._env_dir = os.path.abspath(os.path.join(folder or self._conanfile.recipe_folder, self.env_name))
        self.bin_dir = os.path.join(self._env_dir, "Scripts" if platform.system() == "Windows" else "bin")
        self._python_exe = os.path.join(self.bin_dir, "python.exe" if platform.system() == "Windows" else "python")

    def _conanfile_run(self, command, accepted_returns):
        ret = self._conanfile.run(command, ignore_errors=True, quiet=True)
        if ret not in accepted_returns:
            raise ConanException("Command '%s' failed" % command)
        return ret

    def _check(self, packages):
        packages_to_install = []
        if not os.path.exists(self._env_dir):
            return packages
        for package in packages:
            name, version = (package.split("=")[0], package.split("=")[1]) if "=" in package else (package, "")
            command = f'"{self._python_exe}" -m pip show {name} | grep "{name}"'
            if version:
                command = f'"{self._python_exe}" -m pip show {name} | grep "{version}"'
            if not self._conanfile_run(command, self.accepted_check_codes) != 0:
                packages_to_install.append(package)
        return packages_to_install

    def _install(self, packages):
        venv.EnvBuilder(clear=True, with_pip=True).create(self._env_dir)
        command = f'"{self._python_exe}" -m pip install {" ".join(packages)}'
        return self._conanfile_run(command, self.accepted_install_codes)

    def generate(self):
        """
        Will try to create a conan virtual env to use the python venv in the next steps.
        We need to use this method in the generate step or earlier in order to use this environment in the following steps.
        """
        env = Environment()
        env.prepend_path("PATH", self.bin_dir)
        env.vars(self._conanfile).save_script(self.env_name)

    def install(self, packages):
        """
        Will try to install the list of pip packages passed as a parameter.

        :param packages: try to install the list of pip packages passed as a parameter.
        :return: the return code of the executed pip command.
        """
        packages_to_install = self._check(packages)

        if packages_to_install:
            return self._install(packages_to_install)
        self._conanfile.output.info(f"Pip requirements: {' '.join(packages)} already installed")
