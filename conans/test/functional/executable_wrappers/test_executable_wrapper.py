import unittest
import textwrap

from conans.test.utils.tools import TestClient


class ExecutableWrapperTestCase(unittest.TestCase):
    zlib = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "zlib"

            def package_info(self):
                self.cpp_info.filter_empty = False
    """)

    build_requires = textwrap.dedent("""
        import os
        import stat
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "cmake"
            requires = "zlib/1.0"
            settings = "os"

            def build(self):
                filename = "cmake.cmd" if self.settings.os == "Windows" else "cmake"
                with open(filename, "w") as f:
                    if self.settings.os == "Windows":
                        f.write("@echo on\\n")
                    else:
                        f.write("set -e\\n")
                        f.write("set -x\\n")

                    f.write("echo MY CMAKE!!!\\n")
                    if self.settings.os == "Windows":
                        f.write("echo arguments: %*\\n")
                    else:
                        f.write("echo arguments: $@\\n")

                self.output.info(open(filename).read())

                st = os.stat(filename)
                os.chmod(filename, st.st_mode | stat.S_IEXEC)

            def package(self):
                self.copy("cmake", dst="bin")
                self.copy("cmake.cmd", dst="bin")

            def package_info(self):
                self.cpp_info.exes = ["cmake"]
                #self.env_info.PATH = [os.path.join(self.package_folder, "bin")]
    """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "app"
            requires = "zlib/1.0"
            build_requires = "cmake/1.0"

            def build(self):
                self.run("cmake --version")
    """)

    def test_basic(self):
        t = TestClient()
        t.save({'zlib.py': self.zlib,
                'cmake.py': self.build_requires,
                'app.py': self.conanfile})
        t.run("create zlib.py zlib/1.0@ --profile=default")
        t.run("create cmake.py cmake/1.0@ --profile=default")
        t.run("create app.py app/1.0@ --profile:host=default --profile:build=default")
        print(t.out)
        self.assertIn("MY CMAKE!!!", t.out)
        self.assertIn("arguments: --version", t.out)
