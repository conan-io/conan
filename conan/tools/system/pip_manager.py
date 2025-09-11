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


def _check(conanfile, env_dir, python_exe, name, version, accepted_returns):
    if os.path.exists(env_dir):
        command = f'"{python_exe}" -m pip show {name} | grep "{name}"'
        if version:
            command = f'"{python_exe}" -m pip show {name} | grep "{version}"'
        installed = _conanfile_run(conanfile, command, accepted_returns) != 0
    else:
        installed = False
    return installed


def _install(conanfile, env_dir, python_exe, base_dir, package, name, accepted_returns):
    venv.EnvBuilder(clear=True, with_pip=True).create(env_dir)
    command = f'"{python_exe}" -m pip install {package}'
    _conanfile_run(conanfile, command, accepted_returns)
    env = Environment()
    env.prepend_path("PATH", base_dir)
    env.vars(conanfile).save_script(f"conan_pip_{name}")
    return base_dir


def pip_tool_requires(conanfile, package, output_forlder):
    mode_check = "check"  # Check if installed, fail if not
    mode_install = "install"
    mode_report = "report"  # Only report what would be installed, no check (can run in any system)
    mode_report_installed = "report-installed"  # report installed and missing packages
    accepted_install_codes = [0]
    accepted_check_codes = [0, 1]

    mode = conanfile.conf.get("tools.system.package_manager:mode", default=mode_check)
    name, version = (package.split("=")[0], package.split("=")[1]) if "=" in package else (package, "")

    env_dir = os.path.join(output_forlder or conanfile.folders.generators_folder, f"pip_venv_{name}")
    base_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
    python_exe = os.path.join(base_dir, "python.exe" if platform.system() == "Windows" else "python")

    if mode == mode_report:
        return

    installed = _check(conanfile, env_dir, python_exe, name, version, accepted_check_codes)

    if mode == mode_report_installed:
        return

    if mode == mode_check and not installed:
        raise ConanException("Pip requirement: '{0}' are missing but can't install "
                             "because tools.system.package_manager:mode is '{1}'."
                             "Please set 'tools.system.package_manager:mode' "
                             "to '{2}' in the [conf] section of the profile, "
                             "or in the command line using "
                             "'-c tools.system.package_manager:mode={2}'".format(package,
                                                                                 mode_check,
                                                                                 mode_install))
    elif not installed:
        return _install(conanfile, env_dir, python_exe, base_dir, package, name, accepted_install_codes)
    else:
        conanfile.output.info(f"Pip requirements: {package} already installed")
