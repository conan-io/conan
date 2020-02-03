import platform
import textwrap
import unittest

from conans.test.utils.tools import TestClient


class MesonTest(unittest.TestCase):

    @unittest.skipIf(platform.system() != "Windows", "Needs windows for vcvars")
    def test_vcvars_priority(self):
        # https://github.com/conan-io/conan/issues/5999
        client = TestClient()
        conanfile_vcvars = textwrap.dedent("""
            import os
            from conans import ConanFile, Meson
    
            class HelloConan(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                def build(self):
                    cmake = Meson(self, append_vcvars=True)
                    cmake.configure()

                # CAPTURING THE RUN METHOD
                def run(self, cmd):
                    self.output.info("PATH ENV VAR: %s" % os.getenv("PATH"))
            """)

        client.save({"conanfile.py": conanfile_vcvars})
        client.run('create . pkg/1.0@ -e PATH="MyCustomPath"')
        self.assertIn("pkg/1.0: PATH ENV VAR: MyCustomPath;", client.out)