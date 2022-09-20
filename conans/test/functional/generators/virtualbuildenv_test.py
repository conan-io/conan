import os
import platform
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient
from conans.util.runners import check_output_runner


class VirtualBuildEnvTest(unittest.TestCase):

    @pytest.mark.skipif(platform.system() != "Windows", reason="needs Windows")
    @pytest.mark.tool_visual_studio  # 15
    def test_delimiter_error(self):
        # https://github.com/conan-io/conan/issues/3080
        conanfile = """from conans import ConanFile
class TestConan(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run('install . -g virtualbuildenv -s os=Windows -s compiler="Visual Studio"'
                   ' -s compiler.runtime=MD -s compiler.version=15')
        bat = client.load("environment_build.bat.env")
        self.assertIn("UseEnv=True", bat)
        self.assertIn('CL=-MD -DNDEBUG -O2 -Ob2 %CL%', bat)

    def test_environment_deactivate(self):
        if platform.system() == "Windows":
            """ This test fails. The deactivation script takes the value of some envvars set by
                the activation script to recover the previous values (set PATH=OLD_PATH). As this
                test is running each command in a different shell, the envvar OLD_PATH that has
                been set by the 'activate' script doesn't exist when we run 'deactivate' in a
                different shell...

                TODO: Remove this test
            """
            self.skipTest("This won't work in Windows")

        in_windows = platform.system() == "Windows"
        env_cmd = "set" if in_windows else "env"
        extension = "bat" if in_windows else "sh"

        def env_output_to_dict(env_output):
            env = {}
            for line in env_output.splitlines():
                tmp = line.split("=")
                # OLDPWD is cleared when a child script is started
                if tmp[0] not in ["SHLVL", "_", "PS1", "OLDPWD"]:
                    env[tmp[0]] = tmp[1].replace("\\", "/")
            return env

        def get_cmd(script_name):
            if in_windows:
                return "%s && set" % script_name
            else:
                return "bash -c 'source %s && env'" % script_name

        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class TestConan(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "virtualbuildenv"
            """)
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        output = check_output_runner(env_cmd)
        normal_environment = env_output_to_dict(output)
        client.run("install .")
        act_build_file = os.path.join(client.current_folder, "activate_build.%s" % extension)
        deact_build_file = os.path.join(client.current_folder, "deactivate_build.%s" % extension)
        self.assertTrue(os.path.exists(act_build_file))
        self.assertTrue(os.path.exists(deact_build_file))
        output = check_output_runner(get_cmd(act_build_file))
        activate_environment = env_output_to_dict(output)
        self.assertNotEqual(normal_environment, activate_environment)
        output = check_output_runner(get_cmd(deact_build_file))
        deactivate_environment = env_output_to_dict(output)
        self.assertDictEqual(normal_environment, deactivate_environment)
