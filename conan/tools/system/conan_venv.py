import venv
import platform
import subprocess
import os
import shutil
import pytest
from contextlib import contextmanager


@contextmanager
def system_paths(new_path):
    original_path = os.environ.get('PATH', '')
    try:
        os.environ['PATH'] = f"{new_path}{os.pathsep}{original_path}"
        yield
    finally:
        os.environ['PATH'] = original_path


def conan_env():
    builder = venv.EnvBuilder(clear=True, with_pip=True)
    env_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_env")
    if os.path.exists(env_dir):
        shutil.rmtree(env_dir)
    builder.create(env_dir)

    base_dir = os.path.join(env_dir, "Scripts" if platform.system() == "Windows" else "bin")
    python_exe = os.path.join(base_dir, "python.exe" if platform.system() == "Windows" else "python")

    # Install packages using subprocess and the virtualenv's pip
    packages = ["meson==1.7.1", "cmake==3.24.2"]
    subprocess.run([python_exe, "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True)
    subprocess.run([python_exe, "-m", "pip", "install"] + packages, check=True, capture_output=True)

    with system_paths(base_dir):
        result = subprocess.run(["cmake", "--version"], check=True, capture_output=True, encoding="utf-8")
        assert "3.24.2" in result.stdout
        result = subprocess.run(["meson", "--version"], check=True, capture_output=True, encoding="utf-8")
        assert "1.7.1" in result.stdout

    with pytest.raises(FileNotFoundError):
        subprocess.run(["meson", "--version"], check=True, capture_output=True, encoding="utf-8")


conan_env()
