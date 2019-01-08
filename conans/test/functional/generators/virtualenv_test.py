import os
import shutil
import subprocess
import unittest
from textwrap import dedent

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.tools import OSInfo, which
from conans.test.utils.conanfile import ConanFileMock
from conans.test.utils.tools import TestBufferConanOutput, temp_folder
from conans.util.files import decode_text, load, save_files, to_file_bytes

os_info = OSInfo()


class VirtualEnvIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.test_folder = temp_folder()
        self.generator = VirtualEnvGenerator(ConanFileMock())
        self.generator.env = {
            "PATH": [os.path.join(self.test_folder, "bin")],
            "CFLAGS": ["-O2"],
            "USER_VALUE": r"some value with space and \ (backslash)"
        }
        self.generator.venv_name = "conan_venv_test_prompt"

        trap_files = {
            os.path.join("original path", "conan_original_test_prog"): "",
            os.path.join("bin", "conan_venv_test_prog"): "",
        }
        save_files(self.test_folder, trap_files)
        save_files(self.test_folder, self.generator.content)
        for f in trap_files:
            os.chmod(os.path.join(self.test_folder, f), 0o755)

    def tearDown(self):
        shutil.rmtree(os.path.split(self.test_folder)[0], ignore_errors=True)

    @property
    def subprocess_env(self):
        env = os.environ.copy()
        env["PATH"] = "%s%s%s" % (os.path.join(
            self.test_folder, "original path"), os.pathsep, env.get(
                "PATH", ""))
        env["CFLAGS"] = "-g"
        env["USER_VALUE"] = "original value"
        return env

    @staticmethod
    def load_env(path):
        text = load(path)
        return dict(l.split("=", 1) for l in text.splitlines())

    def do_verification(self, stdout, stderr):
        stdout = decode_text(stdout)
        self.assertFalse(
            stderr, "Running shell resulted in error, output:\n%s" % stdout)
        self.assertRegex(
            stdout,
            r"(?m)^__conan_venv_test_prog_path__=%s.*bin[/\\]conan_venv_test_prog"
            % self.test_folder.replace("\\", "\\\\"),
            "Packaged binary was not found in PATH")
        self.assertRegex(
            stdout,
            r"(?m)^__original_prog_path__=%s.*original path[/\\]conan_original_test_prog"
            % self.test_folder.replace("\\", "\\\\"),
            "Activated environment incorrectly preserved PATH")
        activated_env = VirtualEnvIntegrationTest.load_env(
            os.path.join(self.test_folder, "env_activated.txt"))
        self.assertEqual(
            activated_env["CFLAGS"], "-O2 -g",
            "Environment variable with spaces is set incorrectly")
        self.assertEqual(activated_env["USER_VALUE"],
                         r"some value with space and \ (backslash)",
                         "Custom variable is set incorrectly")
        before_env = VirtualEnvIntegrationTest.load_env(
            os.path.join(self.test_folder, "env_before.txt"))
        after_env = VirtualEnvIntegrationTest.load_env(
            os.path.join(self.test_folder, "env_after.txt"))
        self.assertDictEqual(before_env, after_env,
                             "Environment restored incorrectly")
        return stdout

    def execute_intereactive_shell(self, args, commands):
        shell = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.test_folder,
            env=self.subprocess_env)
        (stdout, stderr) = shell.communicate(to_file_bytes(dedent(commands)))
        return self.do_verification(stdout, stderr)

    @unittest.skipUnless(os_info.is_posix, "needs POSIX")
    def posix_shell_test(self):
        self.execute_intereactive_shell(
            "sh", """\
                env > env_before.txt
                . ./activate.sh
                env > env_activated.txt
                echo __conan_venv_test_prog_path__=$(which conan_venv_test_prog)
                echo __original_prog_path__=$(which conan_original_test_prog)
                deactivate
                env > env_after.txt
                """)

    @unittest.skipUnless(
        os_info.is_posix and which("fish"), "fish shell is not found")
    def fish_shell_test(self):
        self.execute_intereactive_shell(
            "fish", """\
                env > env_before.txt
                . activate.fish
                env > env_activated.txt
                echo __conan_venv_test_prog_path__=(which conan_venv_test_prog)
                echo __original_prog_path__=(which conan_original_test_prog)
                deactivate
                env > env_after.txt
                """)

    @unittest.skipUnless(
        os_info.is_windows or which("pwsh"), "Requires PowerShell (Core)")
    def powershell_test(self):
        powershell_cmd = "powershell.exe" if os_info.is_windows else "pwsh"
        stdout = self.execute_intereactive_shell(
            [powershell_cmd, "-ExecutionPolicy", "RemoteSigned", "-NoLogo"],
            """\
                Get-ChildItem Env: | ForEach-Object {"$($_.Name)=$($_.Value)"} | Out-File -Encoding utf8 -FilePath env_before.txt
                . ./activate.ps1
                Get-ChildItem Env: | ForEach-Object {"$($_.Name)=$($_.Value)"} | Out-File -Encoding utf8 -FilePath env_activated.txt
                Write-Host "__conan_venv_test_prog_path__=$((Get-Command conan_venv_test_prog).Source)"
                Write-Host "__original_prog_path__=$((Get-Command conan_original_test_prog).Source)"
                deactivate
                Get-ChildItem Env: | ForEach-Object {"$($_.Name)=$($_.Value)"} | Out-File -Encoding utf8 -FilePath env_after.txt
                """)
        self.assertIn("conan_venv_test_prompt", stdout,
                      "Custom prompt is not found")

    @unittest.skipUnless(os_info.is_windows and not os_info.is_posix,
                         "Available on Windows only")
    def windows_cmd_test(self):
        stdout = self.execute_intereactive_shell(
            "cmd", """\
                set > env_before.txt
                activate.bat
                set > env_activated.txt
                for /f "usebackq tokens=*" %i in (`where conan_venv_test_prog`) do echo __conan_venv_test_prog_path__=%i
                for /f "usebackq tokens=*" %i in (`where conan_original_test_prog`) do echo __original_prog_path__=%i
                deactivate.bat
                set > env_after.txt
                """)

        self.assertIn("conan_venv_test_prompt", stdout,
                      "Custom prompt is not found")
