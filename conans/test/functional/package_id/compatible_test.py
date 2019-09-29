import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class PythonBuildTest(unittest.TestCase):

    def compatible_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                settings = "os", "compiler"
                def package_id(self):
                    if self.settings.compiler == "gcc":
                        for version in ("4.8", "4.7", "4.6"):
                            info = self.info.copy()
                            info.settings.compiler.version = version
                            self.compatible_ids.append(info)
            """)
        profile = textwrap.dedent("""
        [settings]
        os = Linux
        compiler=gcc
        compiler.version=4.9
        compiler.libcxx=libstdc++
        """)
        client.save({"conanfile.py": conanfile,
                     "myprofile": profile})
        client.run("create . pkg/0.1@user/stable -pr=myprofile")

        client.save({"conanfile.py": GenConanfile().with_require_plain("pkg/0.1@user/stable")})
        client.run("install . -pr=myprofile -s compiler.version=4.8")
        print client.out
        self.assertIn("success", client.out)

