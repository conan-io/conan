import platform
import textwrap
import unittest
import pytest

from conans.test.utils.tools import TestClient


class MesonTest(unittest.TestCase):

    @pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows for vcvars")
    @pytest.mark.tool_visual_studio
    def test_vcvars_priority(self):
        # https://github.com/conan-io/conan/issues/5999
        client = TestClient()
        conanfile_vcvars = textwrap.dedent("""
            import os
            from conans import ConanFile, Meson

            class HelloConan(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                def build(self):
                    meson = Meson(self, append_vcvars=True)
                    meson.configure()

                # CAPTURING THE RUN METHOD
                def run(self, cmd):
                    self.output.info("PATH ENV VAR: %s" % os.getenv("PATH"))
            """)

        client.save({"conanfile.py": conanfile_vcvars})
        client.run('create . pkg/1.0@ -e PATH="MyCustomPath"')
        self.assertIn("pkg/1.0: PATH ENV VAR: MyCustomPath;", client.out)
