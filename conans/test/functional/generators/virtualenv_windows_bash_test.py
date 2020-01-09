import os
import platform
import subprocess
import textwrap
import unittest

from conans.test.functional.generators.virtualenv_test import _load_env_file
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import decode_text


@unittest.skipIf(platform.system() != "Windows", "Only for Windows")
class VirtualenvWindowsBashTestCase(unittest.TestCase):
    """
    We are running the full example inside Bash (generation of environment files and activate/deactivate), so we need
    to use actual Conan recipes and run an example. We cannot use the same approach as in 'virtualenv_test.py', but
    we should test the same cases
    """

    maxDiff = None
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        
        class Recipe(ConanFile):
            def build(self):
                with open("executable.exe", "w+") as f:
                    f.write("echo EXECUTABLE IN PACKAGE!!")
            
            def package(self):
                self.copy("*.exe", dst="bin")

            def package_info(self):
                # Basic variable
                self.env_info.USER_VAR = r"some value with space and \ (backslash)"
                self.env_info.ANOTHER = "data"
                
                # List variable
                self.env_info.WHATEVER = ["list", "other"]
                self.env_info.WHATEVER2.append("list")
                
                # List with spaces
                self.env_info.CFLAGS = ["cflags1", "cflags2"]
                
                # Add something to the path
                self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))
                
    """)

    @classmethod
    def setUpClass(cls):
        cache_folder = os.path.join(temp_folder(path_with_spaces=False), ".conan")
        t = TestClient(cache_folder=cache_folder)
        t.save({"conanfile.py": cls.conanfile})
        t.run("create . name/version@")

        cls.cache_folder = os.path.dirname(t.cache_folder)

    def _run_environment(self):
        stdout, _ = subprocess.Popen(["where", "conan"], stdout=subprocess.PIPE).communicate()
        conan_path = decode_text(stdout).splitlines()[0]  # Get the first one (Windows returns all found)

        # All the commands are listed in a sh file:
        commands_file = os.path.join(self.test_folder, 'commands.sh')
        with open(commands_file, 'w+') as f:
            # Dirty environment
            f.write("export USER_VAR=existing_value\n")
            f.write("export ANOTHER=existing_value\n")
            f.write("export WHATEVER=existing_value\n")
            f.write("export WHATEVER2=existing_value\n")
            f.write("export CFLAGS=existing_value\n")

            f.write("export PATH={}:$PATH\n".format(os.path.dirname(conan_path).replace('\\', '/').replace('C:', '/c')))
            f.write("export CONAN_USER_HOME={}\n".format(self.cache_folder.replace('\\', '/').replace('C:', '/c')))
            f.write("conan install name/version@ -g virtualenv -g virtualrunenv\n")

            f.write("env > env_before.txt\n")
            f.write("echo 'Start to find executable'\n")
            f.write("echo __exec_pre_path__=$(which executable)\n")
            f.write(". ./activate.sh\n")
            f.write("env > env_activated.txt\n")
            f.write("echo __exec_env_path__=$(which executable)\n")
            f.write("executable\n")
            f.write(". ./deactivate.sh\n")
            f.write("echo __exec_post_path__=$(which executable)\n")
            f.write("env > env_after.txt\n")

        cmd = r'C:\Windows\System32\cmd.exe /c ""C:\Program Files\Git\bin\sh.exe" --login -i "{}""'.format(commands_file)
        shell = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.test_folder)
        (stdout, stderr) = shell.communicate()
        stdout, stderr = decode_text(stdout), decode_text(stderr)

        env_before = _load_env_file(os.path.join(self.test_folder, "env_before.txt"))
        env_after = _load_env_file(os.path.join(self.test_folder, "env_after.txt"))
        self.assertDictEqual(env_before, env_after)  # Environment restored correctly

        return stdout, _load_env_file(os.path.join(self.test_folder, "env_activated.txt"))

    def test_basic_variable(self):
        self.test_folder = temp_folder(path_with_spaces=False)
        _, environment = self._run_environment()

        self.assertEqual(environment["USER_VAR"], r"some value with space and \ (backslash)")
        self.assertEqual(environment["ANOTHER"], "data")

    def test_find_program(self):
        self.test_folder = temp_folder(path_with_spaces=False)
        stdout, _ = self._run_environment()

        epaths = dict(line.split("=", 1) for line in reversed(stdout.splitlines()) if line.startswith("__exec_"))
        self.assertEqual(epaths["__exec_pre_path__"], "")
        self.assertEqual(epaths["__exec_post_path__"], "")
        self.assertTrue(len(epaths["__exec_env_path__"]) > 0)
        self.assertIn("EXECUTABLE IN PACKAGE!!", stdout)

    def test_list_variable(self):
        self.test_folder = temp_folder(path_with_spaces=False)
        _, environment = self._run_environment()

        self.assertEqual(environment["WHATEVER"], "list:other:existing_value")
        self.assertEqual(environment["WHATEVER2"], "list:existing_value")

    def test_list_with_spaces(self):
        self.test_folder = temp_folder(path_with_spaces=False)
        _, environment = self._run_environment()

        self.assertEqual(environment["CFLAGS"], "cflags1 cflags2  existing_value")  # FIXME: extra blank
