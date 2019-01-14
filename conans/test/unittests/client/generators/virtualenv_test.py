import platform
import unittest

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.test.utils.conanfile import ConanFileMock


class VirtualEnvGeneratorTest(unittest.TestCase):
    """Verify that VirtualEnvGenerator adds proper values.

    This Unit Test only verifies that proper values are populated
    from ConanFile into self.env.
    The correctness of generated code is verified by
    :class:`.virtualenv_test.VirtualEnvIntegrationTest`
    """

    def virtualenv_test(self):
        conanfile = ConanFileMock()
        conanfile.env["PATH"] = ["bin"]
        conanfile.env["USER_FLAG"] = "user_value"

        gen = VirtualEnvGenerator(conanfile)

        self.assertEqual(
            dict(gen.env), {
                "PATH": ["bin"],
                "USER_FLAG": "user_value"
            })
        self.assertEqual(gen.venv_name, "conanenv")

        generated_files = gen.content
        ext = "bat" if platform.system() == "Windows" else "sh"
        self.assertIn("activate.%s" % ext, generated_files)
