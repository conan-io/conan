import os
import platform
import subprocess
import unittest

from conans import load
from conans.test.utils.tools import TestClient


class VirtualBuildEnvTest(unittest.TestCase):

    def environment_deactivate_test(self):

        in_windows = platform.system() == "Windows"
        env_cmd = "set" if in_windows else "env"
        extension = "bat" if in_windows else "sh"

        def env_output_to_dict(env_output):
            env = {}
            for line in env_output.splitlines():
                tmp = line.decode().split("=")
                if tmp[0] not in ["SHLVL", "_", "PS1"]:
                    env[tmp[0]] = tmp[1].replace("\\", "/")
            return env

        def get_cmd(script_name):
            if in_windows:
                return "%s && set" % script_name
            else:
                return "bash -c 'source %s && env'" % script_name

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
        output = subprocess.check_output(env_cmd, shell=True)
        normal_environment = env_output_to_dict(output)
        client.run("install .")
        act_build_file = os.path.join(client.current_folder, "activate_build.%s" % extension)
        deact_build_file = os.path.join(client.current_folder, "deactivate_build.%s" % extension)
        self.assertTrue(os.path.exists(act_build_file))
        self.assertTrue(os.path.exists(deact_build_file))
        if in_windows:
            act_build_content_len = len(load(act_build_file).splitlines())
            deact_build_content_len = len(load(deact_build_file).splitlines())
            self.assertEqual(act_build_content_len, deact_build_content_len)
        output = subprocess.check_output(get_cmd(act_build_file), shell=True)
        activate_environment = env_output_to_dict(output)
        self.assertNotEqual(normal_environment, activate_environment)
        output = subprocess.check_output(get_cmd(deact_build_file), shell=True)
        deactivate_environment = env_output_to_dict(output)
        self.assertEqual(normal_environment, deactivate_environment)
