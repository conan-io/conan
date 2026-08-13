import os
import platform
import subprocess
import sys
import textwrap

from conan.internal.cache.home_paths import HomePaths
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import default_profiles
from conan.internal.util.files import save


def _run_conan_subprocess(args, conan_home):
    # Real subprocess: TestClient calls Cli.run() directly and skips main(),
    # but main() is exactly what does the fd-level redirection under test.
    env = dict(os.environ)
    env["CONAN_HOME"] = conan_home
    code = "from conans.conan import run; run()"
    _cwd = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    result = subprocess.run([sys.executable, "-c", code] + args, env=env, cwd=_cwd,
                             capture_output=True, text=True)
    return result


def _latest_log(conan_home):
    log_dir = HomePaths(conan_home).command_logs_path
    log_files = sorted(os.listdir(log_dir), key=lambda f: os.path.getmtime(os.path.join(log_dir, f)))
    return os.path.join(log_dir, log_files[-1])


def test_command_log_captures_subprocess_output():
    conan_home = temp_folder()
    save(os.path.join(HomePaths(conan_home).profiles_path, "default"), default_profiles[platform.system()])
    save(HomePaths(conan_home).global_conf_path, "core.log:enabled=True\n")

    pkg_folder = temp_folder()
    python_exe = sys.executable.replace("\\", "/")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "loggytest"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            def build(self):
                self.run("{python_exe} -c \\"print('hello-from-subprocess-build')\\"")
        """)
    save(os.path.join(pkg_folder, "conanfile.py"), conanfile)

    result = _run_conan_subprocess(["create", pkg_folder], conan_home)
    assert result.returncode == 0, result.stderr

    log_path = _latest_log(conan_home)
    content = open(log_path).read()
    assert "# Command: conan create" in content
    assert "hello-from-subprocess-build" in content
    assert "# Exit code: 0 (SUCCESS)" in content


def test_command_log_records_error_exit_code():
    conan_home = temp_folder()
    save(os.path.join(HomePaths(conan_home).profiles_path, "default"), default_profiles[platform.system()])
    save(HomePaths(conan_home).global_conf_path, "core.log:enabled=True\n")

    result = _run_conan_subprocess(["install", "/this/path/does/not/exist"], conan_home)
    assert result.returncode != 0

    log_path = _latest_log(conan_home)
    content = open(log_path).read()
    assert f"# Exit code: {result.returncode} (ERROR_GENERAL)" in content
