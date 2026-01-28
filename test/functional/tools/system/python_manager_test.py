import sys
import textwrap
import platform
import pytest
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save_files
from conan.test.utils.test_files import temp_folder


def _create_py_hello_world(folder):
    setup_py = textwrap.dedent("""
        from setuptools import setup, find_packages

        setup(
            name='hello',
            version='0.1.0',
            packages=find_packages(include=['hello', 'hello.*']),
            entry_points={'console_scripts': ['hello-world = hello:hello']}
        )
        """)
    hello_py = textwrap.dedent("""
        def hello():
            print("Hello Test World!")
        """)

    save_files(folder, {"setup.py": setup_py, "hello/__init__.py": hello_py})


def test_empty_pyenv():
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system import PyEnv

        class PyenvPackage(ConanFile):

            def generate(self):
                PyEnv(self).generate()

            def build(self):
                self.run("python -m pip list")
        """)

    c = TestClient(path_with_spaces=False)
    c.save({"conanfile.py": conanfile})
    c.run("build")
    # Test that some Conan common deps are not in this pip list
    assert "requests" not in c.out
    assert "colorama" not in c.out
    assert "Jinja2" not in c.out
    assert "PyJWT" not in c.out


def test_build_py_manager():
    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pyenv = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PyEnv
        from conan.tools.layout import basic_layout

        class PyenvPackage(ConanFile):
            def layout(self):
                basic_layout(self)

            def generate(self):
                pyenv = PyEnv(self)
                pyenv.install(["{pip_package_folder}"])
                pyenv.generate()

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pyenv})
    client.run("build pip")

    print(client.out)

    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out

    client.run("build pip")
    assert "Found existing installation: hello 0.1.0" in client.out
    assert "Hello Test World!" in client.out


def test_install_version_range():
    c = TestClient(path_with_spaces=False)

    # TODO: Maybe we want a pip.run("-m pip install .") that automatically handles python.exe path
    conanfile_pyenv = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.system import PyEnv
        from conan.tools.layout import basic_layout

        class PyenvPackage(ConanFile):

            def generate(self):
                pyenv = PyEnv(self)
                pyenv.install(["."])
                pyenv.install(["hello>=0.0,<1.0"])
                pyenv.generate()

            def build(self):
                self.run("hello-world")
        """)

    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    c.save({"conanfile.py": conanfile_pyenv})
    _create_py_hello_world(c.current_folder)

    c.run("build")

    assert "RUN: hello-world" in c.out
    assert "Hello Test World!" in c.out


def test_create_py_manager():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pyenv = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PyEnv
        from conan.tools.layout import basic_layout

        class PyenvPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"
            build_policy = "missing"
            upload_policy = "skip"

            def layout(self):
                basic_layout(self)

            def finalize(self):
                PyEnv(self, self.package_folder).install(["{pip_package_folder}"])

            def package_info(self):
                python_env_bin = PyEnv(self, self.package_folder).bin_dir
                self.buildenv_info.prepend_path("PATH", python_env_bin)
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):

            def requirements(self):
                self.tool_requires("pip_hello_test/0.1")

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pyenv, "consumer/conanfile.py": conanfile})
    client.run("create pip --version=0.1")
    client.run("build consumer")

    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out


@pytest.mark.skipif(sys.version_info.minor < 8, reason="UV needs Python >= 3.8")
def test_build_uv_manager():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    def conanfile_pyenv(py_version):
        return textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PyEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PyenvPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                pip_env = PyEnv(self, py_version="{py_version}")
                pip_env.install(["{pip_package_folder}"])
                pip_env.generate()
                pip_env.run(["--version"])

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pyenv("3.11.6")})
    client.run("build pip/conanfile.py")
    assert "Virtual environment for Python 3.11.6 created successfully using UV." in client.out
    if platform.system() == "Windows":
        assert "python.exe --version\nPython 3.11.6" in client.out
    else:
        assert "python --version\nPython 3.11.6" in client.out
    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out

    client.run("build pip/conanfile.py")
    assert "Found existing installation: hello 0.1.0" in client.out
    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out

    client.save({"pip/conanfile.py": conanfile_pyenv("3.12.3")})

    client.run("build pip/conanfile.py")
    assert "Virtual environment for Python 3.12.3 created successfully using UV." in client.out
    if platform.system() == "Windows":
        assert "python.exe --version\nPython 3.12.3" in client.out
    else:
        assert "python --version\nPython 3.12.3" in client.out
    assert "Found existing installation: hello 0.1.0" not in client.out
    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out


@pytest.mark.skipif(sys.version_info.minor < 8, reason="UV needs Python >= 3.8")
def test_fail_build_uv_manager():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pyenv = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PyEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PyenvPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                pip_env = PyEnv(self, py_version="3.11.86")
                pip_env.install(["{pip_package_folder}"])
                pip_env.generate()

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pyenv})
    client.run("build pip/conanfile.py", assert_error=True)
    assert "PyEnv could not create a Python 3.11.86 virtual environment using UV" in client.out


@pytest.mark.skipif(sys.version_info.minor > 7, reason="UV needs Python 3.7 to fail")
def test_fail_uv_python_version():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pyenv = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PyEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PyenvPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                pip_env = PyEnv(self, py_version="3.11.86")
                pip_env.install(["{pip_package_folder}"])
                pip_env.generate()

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pyenv})
    client.run("build pip/conanfile.py", assert_error=True)
    assert "needs Python >= 3.8" in client.out


def test_build_deprecated_python_manager():
    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pyenv = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PipEnv
        from conan.tools.layout import basic_layout

        class PyenvPackage(ConanFile):
            def layout(self):
                basic_layout(self)

            def generate(self):
                pip = PipEnv(self)
                pip.install(["{pip_package_folder}"])
                pip.generate()

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pyenv})
    client.run("build pip")

    assert "WARN: deprecated: 'PipEnv()' is deprecated, use 'PyEnv()'" in client.out
    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out
