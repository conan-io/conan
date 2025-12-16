import textwrap
import platform
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


def test_build_uv_manager():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pip = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import UVEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PipPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                pip_env = UVEnv(self, py_version="3.11.6")
                pip_env.install(["{pip_package_folder}"])
                pip_env.generate()
                pip_env.run(["--version"])

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pip})
    client.run("build pip/conanfile.py")
    assert "Using CPython 3.11.6" in client.out
    assert "Creating virtual environment with seed packages" in client.out
    assert "Virtual environment for Python 3.11.6 created successfully using UV." in client.out
    if platform.system() == "Windows":
        assert "python.exe --version\nPython 3.11.6" in client.out
    else:
        assert "python --version\nPython 3.11.6" in client.out
    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out


def test_fail_build_uv_manager():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pip = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import UVEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PipPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                pip_env = UVEnv(self, py_version="3.11.86")
                pip_env.install(["{pip_package_folder}"])
                pip_env.generate()

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pip})
    client.run("build pip/conanfile.py", assert_error=True)
    print(client.out)
    assert "UVEnv could not create a Python 3.11.86 virtual environment using UV" in client.out


def test_run_uvx():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pip = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import UVEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PipPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                pip_env = UVEnv(self, py_version="3.11.6")
                pip_env.install(["{pip_package_folder}"])
                pip_env.generate()
                pip_env.uvx(["ruff==0.14.9", "--version"])

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)
    # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pip})
    client.run("build pip/conanfile.py")
    assert "Using CPython 3.11.6" in client.out
    assert "Creating virtual environment with seed packages" in client.out
    assert "Virtual environment for Python 3.11.6 created successfully using UV." in client.out
    assert "ruff 0.14.9" in client.out
    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out
