import os
import platform
import subprocess
import unittest

from conans import load
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient
from conans.util.files import decode_text


class VirtualBuildEnvTest(unittest.TestCase):

    def environment_deactivate_test(self):

        in_windows = platform.system() == "Windows"
        env_cmd = "set" if in_windows else "env"
        extension = "bat" if in_windows else "sh"

        def env_output_to_dict(env_output):
            env = {}
            for line in env_output.splitlines():
                tmp = line.decode().split("=")
                # OLDPWD is cleared when a child script is started
                if tmp[0] not in ["SHLVL", "_", "PS1", "OLDPWD"]:
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

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def environment_path_appended_test(self):
        def get_path_from_content(content):
            vars = [line for line in content.splitlines() if line.lower().startswith("set path=")]
            return vars[0].split("=", 1)[-1]
        conanfile = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    settings = "os", "compiler", "arch", "build_type"
    generators = "virtualbuildenv"
"""
        output = decode_text(subprocess.check_output("set", shell=True))
        normal_path = [line for line in output.splitlines() if line.lower().startswith("path=")][0]
        normal_path = normal_path.split("=", 1)[-1]
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        activate_content = load(os.path.join(client.current_folder, "activate_build.bat"))
        activate_path = get_path_from_content(activate_content)
        self.assertNotIn(normal_path, activate_path)
        self.assertIn("PATH", activate_path)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Windows")
    def activate_and_activate_build_test(self):
        """
        Check %PATH% is being effectively used when loading consecutive virualrunenv &
        virtualbuildenv scripts.
        https://github.com/conan-io/conan/issues/3038
        """
        conanfile_dep = """
import os
from conans import ConanFile

class TestConan(ConanFile):
    name = "dep"
    version = "1.0"
    settings = "os", "compiler", "arch", "build_type"
    exports = "*.exe"
    
    def package(self):
        self.copy("*.exe", dst="bin")
"""
        conanfile = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "test"
    version = "1.0"
    settings = "os", "compiler", "arch", "build_type"
    requires = "dep/1.0@danimtb/testing"
    generators = "virtualrunenv", "virtualbuildenv"
"""
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile_dep,
                     "fake.exe": "content"})
        client.run("create . danimtb/testing")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("install .")
        run_path = os.path.join(client.current_folder, "activate_run.bat")
        build_path = os.path.join(client.current_folder, "activate_build.bat")
        output = decode_text(subprocess.check_output("%s && %s && set" % (run_path, build_path), shell=True))
        pkg_path = client.paths.packages(ConanFileReference("dep", "1.0", "danimtb", "testing"))
        path = os.path.join(pkg_path, "6cc50b139b9c3d27b3e9042d5f5372d327b3a9f7", "bin")
        self.assertIn(path, output)
