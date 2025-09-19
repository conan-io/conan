import venv
import platform
import os

from conan.errors import ConanException
from conan.tools.env.environment import Environment


def _conanfile_run(conanfile, command, accepted_returns):
    ret = conanfile.run(command, ignore_errors=True, quiet=True)
    if ret not in accepted_returns:
        raise ConanException("Command '%s' failed" % command)
    return ret


def _check(conanfile, env_dir, python_exe, packages, accepted_returns):
    # FIXME: Local pip python package path
    packages_to_install = []
    if not os.path.exists(env_dir):
        return packages
    for package in packages:
        name, version = (package.split("=")[0], package.split("=")[1]) if "=" in package else (package, "")
        command = f'"{python_exe}" -m pip show {name} | grep "{name}"'
        if version:
            command = f'"{python_exe}" -m pip show {name} | grep "{version}"'
        if not _conanfile_run(conanfile, command, accepted_returns) != 0:
            packages_to_install.append(package)
    return packages_to_install


def _install(conanfile, env_dir, python_exe, base_dir, packages, accepted_returns):
    venv.EnvBuilder(clear=True, with_pip=True).create(env_dir)
    command = f'"{python_exe}" -m pip install {" ".join(packages)}'
    _conanfile_run(conanfile, command, accepted_returns)
    env = Environment()
    env.prepend_path("PATH", base_dir)
    env.vars(conanfile).save_script(f"conan_pip_{conanfile.name}")
    return base_dir


def pip_tool_requires(conanfile, packages, output_forlder=None):
    accepted_install_codes = [0]
    accepted_check_codes = [0, 1]

    env_dir = os.path.join(output_forlder or conanfile.package_folder, f"pip_venv_{conanfile.name}")
    base_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
    python_exe = os.path.join(base_dir, "python.exe" if platform.system() == "Windows" else "python")

    packages_to_install = _check(conanfile, env_dir, python_exe, packages, accepted_check_codes)

    if packages_to_install:
        return _install(conanfile, env_dir, python_exe, base_dir, packages_to_install, accepted_install_codes)
    else:
        conanfile.output.info(f"Pip requirements: {' '.join(packages)} already installed")
