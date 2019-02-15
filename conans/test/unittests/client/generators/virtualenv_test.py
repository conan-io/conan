import platform
import unittest

from conans import ConanFile, Settings
from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.model.env_info import EnvValues
from conans.test.utils.tools import TestBufferConanOutput


class VirtualenvGeneratorTest(unittest.TestCase):

    def prepend_values_test(self):
        """
        Check list values are only prepended once
        """
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues.loads("PATH=[1,2,three]"))
        gen = VirtualEnvGenerator(conanfile)
        content = gen.content
        self.assertIn("PATH=\"1\":\"2\":\"three\"${PATH+:$PATH}", content["activate.sh"])
        if platform.system() == "Windows":
            self.assertIn("PATH=1;2;three;%PATH%", content["activate.bat"])
