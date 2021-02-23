import os
import platform
import subprocess
import textwrap
import unittest

import pytest

from conans.test.functional.generators.virtualenv_test import _load_env_file
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import decode_text, save


@pytest.mark.skipif(platform.system() != "Windows", reason="Only for Windows")
class VirtualenvWindowsBashTestCase(unittest.TestCase):
    """
    We are running the full example inside Bash (generation of environment files and activate/deactivate), so we need
    to use actual Conan recipes and run an example. We cannot use the same approach as in 'virtualenv_test.py', but
    we should test the same cases
    """

    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, tools

        class Recipe(ConanFile):
            def build(self):
                tools.save("executable.exe", "echo EXECUTABLE IN PACKAGE!!")

            def package(self):
                self.copy("*.exe", dst="bin")

            def package_info(self):
                # Basic variable
                self.env_info.USER_VAR = r"some value with space and \\ (backslash)"
                self.env_info.ANOTHER = "data"

                # List variable
                self.env_info.WHATEVER = ["list", "other"]
                self.env_info.WHATEVER2.append("list")

                # List with spaces
                self.env_info.CFLAGS = ["cflags1", "cflags2"]

                # Add something to the path
                self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))

    """)

    @pytest.mark.tool_conan
    def test_git_shell(self):
        test_folder = temp_folder(path_with_spaces=False)

        cache_folder = os.path.join(temp_folder(path_with_spaces=False), ".conan")
        t = TestClient(cache_folder=cache_folder)
        t.save({"conanfile.py": self.conanfile})
        t.run("create . name/version@")

        # Locate the Conan we are actually using (it should be the one in this commit)
        stdout, _ = subprocess.Popen(["where", "conan"], stdout=subprocess.PIPE).communicate()
        conan_path = decode_text(stdout).splitlines()[0]  # Get the first one (Windows returns all found)

        # All the commands are listed in a sh file:
        commands_file = os.path.join(test_folder, 'commands.sh')
        conan_path = os.path.dirname(conan_path).replace('\\', '/').replace('C:', '/c')
        conan_user_home = os.path.dirname(t.cache_folder).replace('\\', '/').replace('C:', '/c')
        save(commands_file, textwrap.dedent("""
            export USER_VAR=existing_value
            export ANOTHER=existing_value
            export WHATEVER=existing_value
            export WHATEVER2=existing_value
            export CFLAGS=existing_value

            export PATH={conan_path}:$PATH
            export CONAN_USER_HOME={conan_user_home}
            conan install name/version@ -g virtualenv -g virtualrunenv

            env > env_before.txt
            echo 'Start to find executable'
            echo __exec_pre_path__=$(which executable)
            . ./activate.sh
            env > env_activated.txt
            echo __exec_env_path__=$(which executable)
            executable
            . ./deactivate.sh
            echo __exec_post_path__=$(which executable)
            env > env_after.txt
        """.format(conan_path=conan_path, conan_user_home=conan_user_home)))

        cmd = r'C:\Windows\System32\cmd.exe /c ""C:\Program Files\Git\bin\sh.exe" --login -i "{}""'.format(commands_file)
        shell = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=test_folder)
        (stdout, stderr) = shell.communicate()
        stdout, stderr = decode_text(stdout), decode_text(stderr)

        env_before = _load_env_file(os.path.join(test_folder, "env_before.txt"))
        env_after = _load_env_file(os.path.join(test_folder, "env_after.txt"))
        self.assertDictEqual(env_before, env_after)  # Environment restored correctly

        # Environment once activated
        environment = _load_env_file(os.path.join(test_folder, "env_activated.txt"))

        # Test a basic variable
        self.assertEqual(environment["USER_VAR"], r"some value with space and \ (backslash)")
        self.assertEqual(environment["ANOTHER"], "data")

        # Test find program
        epaths = dict(line.split("=", 1) for line in reversed(stdout.splitlines()) if line.startswith("__exec_"))
        self.assertEqual(epaths["__exec_pre_path__"], "")
        self.assertEqual(epaths["__exec_post_path__"], "")
        self.assertTrue(len(epaths["__exec_env_path__"].strip()) > 0)
        self.assertIn("EXECUTABLE IN PACKAGE!!", stdout)

        # Test variable which is a list
        self.assertEqual(environment["WHATEVER"], "list:other:existing_value")
        self.assertEqual(environment["WHATEVER2"], "list:existing_value")

        # Variable: list with spaces
        self.assertEqual(environment["CFLAGS"], "cflags1 cflags2 existing_value")
