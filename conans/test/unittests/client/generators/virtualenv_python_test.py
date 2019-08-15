import platform
import unittest

from conans import ConanFile, Settings
from conans.client.generators.virtualenv_python import VirtualEnvPythonGenerator
from conans.model.env_info import EnvValues
from conans.test.utils.tools import TestBufferConanOutput
from conans.model.env_info import DepsEnvInfo


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
        content = gen.content

        file_extension = {"Linux": ".sh", "Windows": ".bat"}.get(platform.system(), default=".sh")
        delimiter = {"Linux": ":", "Windows": ";"}[platform.system()]

        actual_pythonpath_value = [
            line
            for line in content["activate_run" + file_extension].splitlines()
            if line.startswith("PYTHONPATH")
        ][0].split("=")[1]

        assert actual_pythonpath_value.endswith("${PYTHONPATH+:$PYTHONPATH}")

        actual_pythonpath_set = set(
            actual_pythonpath_value[: -len("${PYTHONPATH+:$PYTHONPATH}")].split(
                delimiter
            )
        )

        assert actual_pythonpath_set == set(
            ['"1"', '"2"', '"three"', '"DepAPath"', '"DepBPath"']
        )
