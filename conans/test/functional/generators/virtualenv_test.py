import os
import unittest
from subprocess import PIPE, Popen

import six
from parameterized.parameterized import parameterized

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.tools import OSInfo
from conans.test.utils.conanfile import ConanFileMock
from conans.test.utils.tools import temp_folder
from conans.util.files import decode_text, load, save_files, to_file_bytes

os_info = OSInfo()


class PosixShellCommands(object):
    shell = "sh"
    activate = ". ./activate.sh"
    deactivate = ". ./deactivate.sh"
    dump_env = "env > {filename}"
    find_program = "echo {variable}=$(which {program})"

    skip = not os_info.is_posix


class PowerShellCommands(object):
    shell = [
        "powershell.exe" if os_info.is_windows else "pwsh", "-ExecutionPolicy",
        "RemoteSigned", "-NoLogo"
    ]
    activate = ". ./activate.ps1"
    deactivate = ". ./deactivate.ps1"
    dump_env = 'Get-ChildItem Env: | ForEach-Object {{"$($_.Name)=$($_.Value)"}} | Out-File -Encoding utf8 -FilePath {filename}'
    find_program = 'Write-Host "{variable}=$((Get-Command {program}).Source)"'

    # Change to this once support for PowreShell Core is in place.
    # skip = not (os_info.is_windows or which("pwsh"))
    skip = (not os_info.is_windows) or os_info.is_posix


class WindowsCmdCommands(object):
    shell = "cmd"
    activate = "activate.bat"
    deactivate = "deactivate.bat"
    dump_env = "set > {filename}"
    find_program = 'for /f "usebackq tokens=*" %i in (`where {program}`) do echo {variable}=%i'

    skip = (not os_info.is_windows) or os_info.is_posix


def load_env(path, file_name):
    text = load(os.path.join(path, file_name))
    return dict(l.split("=", 1) for l in text.splitlines())


def name_func(func, _num, params):
    return "%s_%s" % (func.__name__, params.args[0].__class__.__name__)


class VirtualEnvIntegrationTest(unittest.TestCase):
    @parameterized.expand([
        (PosixShellCommands(), ),
        (PowerShellCommands(), ),
        (WindowsCmdCommands(), ),
    ], name_func)
    def activate_deactivate_test(self, commands):
        if commands.skip:
            self.skipTest("No supported shell found")

        test_folder = temp_folder()

        program_candidates = {
            os.path.join("original path", "conan_original_test_prog"): "",
            os.path.join("bin", "conan_venv_test_prog"): "",
        }
        save_files(test_folder, program_candidates)
        for f in program_candidates:
            os.chmod(os.path.join(test_folder, f), 0o755)

        generator = VirtualEnvGenerator(ConanFileMock())
        generator.env = {
            "PATH": [os.path.join(test_folder, "bin")],
            "CFLAGS": ["-O2"],
            # https://github.com/conan-io/conan/issues/3080
            "CL": ["-MD", "-DNDEBUG", "-O2", "-Ob2"],
            "USER_VALUE": r"some value with space and \ (backslash)"
        }
        generator.venv_name = "conan_venv_test_prompt"
        save_files(test_folder, generator.content)

        preactivate_env = os.environ.copy()
        preactivate_env["PATH"] = "%s%s%s" % (os.path.join(
            test_folder, "original path"), os.pathsep,
                                              preactivate_env.get("PATH", ""))
        preactivate_env["CFLAGS"] = "-g"
        preactivate_env["CL"] = "-DWIN32"
        preactivate_env["USER_VALUE"] = "original value"

        shell_commands = "\n".join([
            commands.dump_env.format(filename="env_before.txt"),
            commands.activate,
            commands.dump_env.format(filename="env_activated.txt"),
            commands.find_program.format(
                program="conan_venv_test_prog",
                variable="__conan_venv_test_prog_path__"),
            commands.find_program.format(
                program="conan_original_test_prog",
                variable="__original_prog_path__"),
            commands.deactivate,
            commands.dump_env.format(filename="env_after.txt"),
            "",
        ])

        shell = Popen(commands.shell, stdin=PIPE, stdout=PIPE, stderr=PIPE,
            cwd=test_folder, env=preactivate_env)
        (stdout, stderr) = shell.communicate(to_file_bytes(shell_commands))
        stdout = decode_text(stdout)

        self.assertFalse(
            stderr, "Running shell resulted in error, output:\n%s" % stdout)
        six.assertRegex(
            self, stdout,
            r"(?m)^__conan_venv_test_prog_path__=%s.*bin[/\\]conan_venv_test_prog"
            % test_folder.replace("\\", "\\\\"),
            "Packaged binary was not found in PATH")
        six.assertRegex(
            self, stdout,
            r"(?m)^__original_prog_path__=%s.*original path[/\\]conan_original_test_prog"
            % test_folder.replace("\\", "\\\\"),
            "Activated environment incorrectly preserved PATH")
        activated_env = load_env(test_folder, "env_activated.txt")
        self.assertEqual(
            activated_env["CFLAGS"], "-O2 -g",
            "Environment variable with spaces is set incorrectly")
        self.assertEqual(
            activated_env["CL"], "-MD -DNDEBUG -O2 -Ob2 -DWIN32"
        )
        self.assertEqual(activated_env["USER_VALUE"],
                         r"some value with space and \ (backslash)",
                         "Custom variable is set incorrectly")
        # TODO: This currently doesn't pass because deactivate restores values
        #       as they were at the moment of running "conan install".
        #       so if variable had different value at the moment of running
        #       activate it won't be restored properly.
        # before_env = load_env(test_folder, "env_before.txt")
        # after_env = load_env(test_folder, "env_after.txt")
        # self.assertDictEqual(before_env, after_env,
        #                      "Environment restored incorrectly")
