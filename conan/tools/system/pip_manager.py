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


def pip_tool_requires(conanfile, packages, output_forlder):
    mode_check = "check"  # Check if installed, fail if not
    mode_install = "install"
    mode_report = "report"  # Only report what would be installed, no check (can run in any system)
    mode_report_installed = "report-installed"  # report installed and missing packages
    accepted_install_codes = [0]
    accepted_check_codes = [0, 1]

    mode = conanfile.conf.get("tools.system.package_manager:mode", default=mode_check)

    env_dir = os.path.join(output_forlder or conanfile.folders.generators_folder, f"pip_venv_{conanfile.name}")
    base_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
    python_exe = os.path.join(base_dir, "python.exe" if platform.system() == "Windows" else "python")

    if mode == mode_report:
        return

    packages_to_install = _check(conanfile, env_dir, python_exe, packages, accepted_check_codes)

    if mode == mode_report_installed:
        return

    if mode == mode_check and packages_to_install:
        raise ConanException("Pip requirement: '{0}' are missing but can't install "
                             "because tools.system.package_manager:mode is '{1}'."
                             "Please set 'tools.system.package_manager:mode' "
                             "to '{2}' in the [conf] section of the profile, "
                             "or in the command line using "
                             "'-c tools.system.package_manager:mode={2}'".format(" ".join(packages),
                                                                                 mode_check,
                                                                                 mode_install))
    elif packages_to_install:
        return _install(conanfile, env_dir, python_exe, base_dir, packages_to_install, accepted_install_codes)
    else:
        conanfile.output.info(f"Pip requirements: {' '.join(packages)} already installed")
