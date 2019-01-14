import platform
import unittest

from conans.client.generators.virtualrunenv import VirtualRunEnvGenerator
from conans.test.utils.conanfile import ConanFileMock


class VirtualRunEnvGeneratorTest(unittest.TestCase):
    """Verify that VirtualRunEnvGenerator adds proper values.

    This Unit Test only verifies that proper values are populated
    from ConanFile into self.env.
    The correctness of generated code is verified by
    :class:`.virtualenv_test.VirtualEnvIntegrationTest`
    """
    def runenv_test(self):
        conanfile = ConanFileMock()
        conanfile.deps_cpp_info["hello"].bin_paths = ["bin2"]
        conanfile.deps_cpp_info["hello"].lib_paths = ["lib2"]

        gen = VirtualRunEnvGenerator(conanfile)

        self.assertEqual(
            gen.env, {
                "PATH": ["bin2"],
                "LD_LIBRARY_PATH": ["lib2"],
                "DYLD_LIBRARY_PATH": ["lib2"],
            })
        self.assertEqual(gen.venv_name, "conanrunenv")

        generated_files = gen.content
        ext = "bat" if platform.system() == "Windows" else "sh"
        self.assertIn("activate_run.%s" % ext, generated_files)
