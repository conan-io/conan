import unittest

from conans import ConanFile, Settings
from conans.client.generators.virtualenv_python import VirtualEnvPythonGenerator
from conans.model.env_info import DepsEnvInfo
from conans.model.env_info import EnvValues
from conans.test.utils.mocks import TestBufferConanOutput


class VirtualEnvPythonGeneratorTest(unittest.TestCase):

    def pythonpath_test(self):
        """
        Check PYTHONPATH env variable
        """
        conanfile = ConanFile(TestBufferConanOutput(), None)
        conanfile.initialize(Settings({}), EnvValues.loads("PYTHONPATH=[1,2,three]"))
        conanfile.deps_env_info = DepsEnvInfo.loads(
            '[ENV_A]\nPYTHONPATH=["DepAPath"]\n[ENV_B]\nPYTHONPATH=["DepBPath"]'
        )
        gen = VirtualEnvPythonGenerator(conanfile)
        gen.output_path = "not-used"
        content = gen.content

        self.assertIn('PYTHONPATH="1":"2":"three":"DepAPath":"DepBPath"${PYTHONPATH+:$PYTHONPATH}',
                      content["environment_run_python.sh.env"])

