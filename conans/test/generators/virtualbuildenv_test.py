import os
import platform
import stat
import subprocess
import unittest

from conans import load
from conans.test.utils.tools import TestClient


class VirtualBuildEnvTest(unittest.TestCase):

    def environment_deactivate_test(self):

        def env_output_to_dict(env_output):
            env = {}
            for line in env_output.splitlines():
                tmp = line.decode().split("=")
                env[tmp[0]] = tmp[1].replace("\\", "/")
            return env

        conanfile = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    settings = "os", "compiler", "arch", "build_type"
    generators = "virtualbuildenv"
"""
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        env_cmd = "set" if platform.system() == "Windows" else "env"
        extension = "bat" if platform.system() == "Windows" else "sh"
        output = subprocess.check_output(env_cmd, shell=True)
        normal_environment = env_output_to_dict(output)
        client.run("install .")
        activate_build_file = os.path.join(client.current_folder, "activate_build.%s" % extension)
        deactivate_build_file = os.path.join(client.current_folder,
                                             "deactivate_build.%s" % extension)
        if platform.system() == "Windows":
            activate_build_content = load(activate_build_file)
            deactivate_build_content = load(deactivate_build_file)
            self.assertEqual(len(activate_build_content.splitlines()),
                             len(deactivate_build_content.splitlines()))
        os.chmod(activate_build_file, stat.S_IEXEC)
        os.chmod(deactivate_build_file, stat.S_IEXEC)
        output = subprocess.check_output(activate_build_file + " && %s" % env_cmd, shell=True)
        activate_environment = env_output_to_dict(output)
        self.assertNotEqual(normal_environment, activate_environment)
        output = subprocess.check_output(deactivate_build_file + " && %s" % env_cmd, shell=True)
        deactivate_environment = env_output_to_dict(output)
        self.assertEqual(normal_environment, deactivate_environment)
