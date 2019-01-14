import platform
import unittest

from conans.client.generators.virtualbuildenv import VirtualBuildEnvGenerator
from conans.test.utils.conanfile import ConanFileMock, MockSettings


class VirtualBuildEnvGeneratorTest(unittest.TestCase):
    """Verify that VirtualBuildEnvGenerator adds proper values.

    This Unit Test only verifies that proper values are populated
    from ConanFile into self.env.
    The correctness of generated code is verified by
    :class:`.virtualenv_test.VirtualEnvIntegrationTest`
    """

    def gcc_test(self):
        conanfile = ConanFileMock()
        conanfile.settings = MockSettings({"compiler": "gcc"})

        gen = VirtualBuildEnvGenerator(conanfile)

        self.assertEqual(
            sorted(gen.env.keys()),
            sorted(["CPPFLAGS", "CXXFLAGS", "CFLAGS", "LDFLAGS", "LIBS"]))
        self.assertEqual(gen.venv_name, "conanbuildenv")

        generated_files = gen.content
        ext = "bat" if platform.system() == "Windows" else "sh"
        self.assertIn("activate_build.%s" % ext, generated_files)

    @unittest.skipUnless(platform.system() == "Windows", "needs Windows")
    def visualstudio_test(self):
        conanfile = ConanFileMock()
        conanfile.settings = MockSettings({
            "compiler": "Visual Studio",
            "compiler.version": "15",
            "compiler.runtime": "MD",
            "build_type": "Release"
        })

        gen = VirtualBuildEnvGenerator(conanfile)

        self.assertEqual(["-MD", "-DNDEBUG", "-O2", "-Ob2"], gen.env["CL"])
        self.assertIn("CL", gen.env)
        self.assertIn("LIB", gen.env)
        self.assertIn("_LINK_", gen.env)

        generated_files = gen.content
        ext = "bat" if platform.system() == "Windows" else "sh"
        self.assertIn("activate_build.%s" % ext, generated_files)
