import venv
import platform
import os
from contextlib import contextmanager

from conan.errors import ConanException
from conan.tools.env.environment import Environment


@contextmanager
def python_tools_system_paths(new_path):
    original_path = os.environ.get('PATH', '')
    try:
        os.environ['PATH'] = f"{new_path}{os.pathsep}{original_path}"
        yield
    finally:
        os.environ['PATH'] = original_path


# def conan_env():
#     builder = venv.EnvBuilder(clear=True, with_pip=True)
#     env_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_env")
#     if os.path.exists(env_dir):
#         shutil.rmtree(env_dir)
#     builder.create(env_dir)

#     base_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
#     python_exe = os.path.join(base_dir, "python.exe" if platform.system() == "Windows" else "python")

#     # Install packages using subprocess and the virtualenv's pip
#     packages = ["meson==1.7.1", "cmake==3.24.2"]
#     subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True)
#     subprocess.run([python_exe, "-m", "pip", "install"] + packages, check=True, capture_output=True)

#     with python_tools_system_paths(base_dir):
#         result = subprocess.run(["cmake", "--version"], check=True, capture_output=True, encoding="utf-8")
#         assert "3.24.2" in result.stdout
#         result = subprocess.run(["meson", "--version"], check=True, capture_output=True, encoding="utf-8")
#         assert "1.7.1" in result.stdout

#     with pytest.raises(FileNotFoundError):
#         subprocess.run(["meson", "--version"], check=True, capture_output=True, encoding="utf-8")


# conan_env()


def pip_tool_requires(conanfile, package):
    mode_check = "check"  # Check if installed, fail if not
    mode_install = "install"
    mode_report = "report"  # Only report what would be installed, no check (can run in any system)
    mode_report_installed = "report-installed"  # report installed and missing packages
    accepted_install_codes = [0]
    accepted_check_codes = [0, 1]

    mode = conanfile.conf.get("tools.system.package_manager:mode", default=mode_check)
    name, version = (package.split("=")[0], package.split("=")[1]) if "=" in package else (package, "")

    builder = venv.EnvBuilder(clear=True, with_pip=True)
    env_dir = os.path.join(conanfile.folders.generators_folder, f"pip_venv_{name}")
    base_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
    python_exe = os.path.join(base_dir, "python.exe" if platform.system() == "Windows" else "python")

    def conanfile_run(command, accepted_returns):
        ret = conanfile.run(command, ignore_errors=True, quiet=True)
        if ret not in accepted_returns:
            raise ConanException("Command '%s' failed" % command)
        return ret

    if mode == mode_report:
        return

    if os.path.exists(env_dir):
        command = f'{python_exe} -m pip show {name} | grep "{name}"'
        if version:
            command = f'{python_exe} -m pip show {name} | grep "{version}"'
        installed = conanfile_run(command, accepted_check_codes) != 0
    else:
        installed = False

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
        builder.create(env_dir)
        command = f"{python_exe} -m pip install {package}"
        conanfile_run(command, accepted_install_codes)
        env = Environment()
        env.prepend_path("PATH", base_dir)
        env.vars(conanfile).save_script(f"conan_pip_{name}")
        return base_dir
    else:
        conanfile.output.info(f"Pip requirements: {package} already installed")
