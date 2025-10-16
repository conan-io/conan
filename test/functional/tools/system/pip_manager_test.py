import textwrap
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


def test_build_pip_manager():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pip = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PipEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PipPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"

            def layout(self):
                basic_layout(self)

            def generate(self):
                PipEnv(self).install(["{pip_package_folder}"])
                PipEnv(self).generate()

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)  # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pip})
    client.run("build pip/conanfile.py")

    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out


def test_create_pip_manager():

    pip_package_folder = temp_folder(path_with_spaces=True)
    _create_py_hello_world(pip_package_folder)
    pip_package_folder = pip_package_folder.replace('\\', '/')

    conanfile_pip = textwrap.dedent(f"""
        from conan import ConanFile
        from conan.tools.system import PipEnv
        from conan.tools.layout import basic_layout
        import platform
        import os


        class PipPackage(ConanFile):
            name = "pip_hello_test"
            version = "0.1"
            build_policy = "missing"
            upload_policy = "skip"

            def layout(self):
                basic_layout(self)

            def finalize(self):
                PipEnv(self, self.package_folder).install(["{pip_package_folder}"])

            def package_info(self):
                python_env_bin = PipEnv(self, self.package_folder).bin_dir
                self.buildenv_info.prepend_path("PATH", python_env_bin)
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile


        class Recipe(ConanFile):
            name = "pip_test"
            version = "0.1"

            def requirements(self):
                self.tool_requires("pip_hello_test/0.1")

            def build(self):
                self.run("hello-world")
        """)

    client = TestClient(path_with_spaces=False)  # FIXME: the python shebang inside vitual env packages fails when using path_with_spaces
    client.save({"pip/conanfile.py": conanfile_pip, "consumer/conanfile.py": conanfile})
    client.run("create pip/conanfile.py --version=0.1")
    client.run("build consumer/conanfile.py")

    assert "RUN: hello-world" in client.out
    assert "Hello Test World!" in client.out
