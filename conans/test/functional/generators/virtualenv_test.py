import os
import platform
import subprocess
import unittest
from collections import OrderedDict

import pytest
import six
from parameterized.parameterized import parameterized_class

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.tools import OSInfo, files as tools_files
from conans.client.tools.env import environment_append
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.util.files import decode_text, load, save_files, to_file_bytes


os_info = OSInfo()


def _load_env_file(filename):
    return dict(l.split("=", 1) for l in load(filename).splitlines())


class PosixShellCommands(object):
    id = shell = "sh"
    activate = ". ./activate.sh"
    deactivate = ". ./deactivate.sh"
    dump_env = "env > {filename}"
    find_program = "echo {variable}=$(which {program})"

    @property
    def skip(self):
        return not os_info.is_posix


class PowerShellCommands(object):
    id = "ps1"
    shell = [
        "powershell.exe" if os_info.is_windows else "pwsh", "-ExecutionPolicy",
        "RemoteSigned", "-NoLogo"
    ]
    activate = ". ./activate.ps1"
    deactivate = ". ./deactivate.ps1"
    dump_env = 'Get-ChildItem Env: | ForEach-Object {{"$($_.Name)=$($_.Value)"}} | Out-File -Encoding utf8 -FilePath {filename}'
    find_program = 'Write-Host "{variable}=$((Get-Command {program}).Source)"'

    @property
    def skip(self):
        return not (os_info.is_windows or tools_files.which("pwsh"))


class WindowsCmdCommands(object):
    id = shell = "cmd"
    activate = "activate.bat"
    deactivate = "deactivate.bat"
    dump_env = "set > {filename}"
    find_program = 'for /f "usebackq tokens=*" %i in (`where {program}`) do echo {variable}=%i'

    @property
    def skip(self):
        return (not os_info.is_windows) or os_info.is_posix


@parameterized_class([{"commands": PosixShellCommands()},
                      {"commands": PowerShellCommands()},
                      {"commands": WindowsCmdCommands()}, ])
class VirtualEnvIntegrationTestCase(unittest.TestCase):
    env_before = "env_before.txt"
    env_activated = "env_activated.txt"
    env_after = "env_after.txt"
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        if cls.commands.skip:
            raise unittest.SkipTest("No support for shell '{}' found".format(cls.commands.shell))

    def setUp(self):
        self.test_folder = temp_folder()
        self.app = "executable"
        self.ori_path = os.path.join(self.test_folder, "ori")
        self.env_path = os.path.join(self.test_folder, "env")
        program_candidates = {os.path.join(self.ori_path, self.app): "",
                              os.path.join(self.env_path, self.app): ""}
        save_files(self.test_folder, program_candidates)
        for p, _ in program_candidates.items():
            os.chmod(os.path.join(self.test_folder, p), 0o755)

    def _run_virtualenv(self, generator):
        generator.output_path = self.test_folder
        save_files(self.test_folder, generator.content)

        # Generate the list of commands to execute
        shell_commands = [
            self.commands.dump_env.format(filename=self.env_before),
            self.commands.find_program.format(program="conan", variable="__conan_pre_path__"),
            self.commands.find_program.format(program=self.app, variable="__exec_pre_path__"),
            self.commands.activate,
            self.commands.dump_env.format(filename=self.env_activated),
            self.commands.find_program.format(program="conan", variable="__conan_env_path__"),
            self.commands.find_program.format(program=self.app, variable="__exec_env_path__"),
            self.commands.deactivate,
            self.commands.dump_env.format(filename=self.env_after),
            self.commands.find_program.format(program="conan", variable="__conan_post_path__"),
            self.commands.find_program.format(program=self.app, variable="__exec_post_path__"),
            "",
        ]

        # Execute
        with environment_append({"PATH": [self.ori_path, ]}):
            shell = subprocess.Popen(self.commands.shell, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, cwd=self.test_folder)
            (stdout, stderr) = shell.communicate(to_file_bytes("\n".join(shell_commands)))
        stdout, stderr = decode_text(stdout), decode_text(stderr)

        # Consistency checks
        self.assertFalse(stderr, "Running shell resulted in error, output:\n%s" % stdout)

        env_before = _load_env_file(os.path.join(self.test_folder, self.env_before))
        env_after = _load_env_file(os.path.join(self.test_folder, self.env_after))
        there_was_ps1 = os.getenv("PS1")
        # FIXME: Not the best behavior
        # The deactivate sets PS1 always, but sometimes it didn't exist previously
        if platform.system() == "Darwin" or not there_was_ps1:
            env_after.pop(six.u("PS1"), None)  # TODO: FIXME: Needed for the test to pass
            env_after.pop("PS1", None)  # TODO: FIXME: Needed for the test to pass

        self.assertDictEqual(env_before, env_after)  # Environment restored correctly
        return stdout, _load_env_file(os.path.join(self.test_folder, self.env_activated))

    @pytest.mark.tool_conan
    def test_basic_variable(self):
        generator = VirtualEnvGenerator(ConanFileMock())
        generator.env = {"USER_VAR": r"some value with space and \ (backslash)",
                         "ANOTHER": "data"}

        _, environment = self._run_virtualenv(generator)

        self.assertEqual(environment["USER_VAR"], r"some value with space and \ (backslash)")
        self.assertEqual(environment["ANOTHER"], "data")

        with environment_append({"USER_VAR": "existing value", "ANOTHER": "existing_value"}):
            _, environment = self._run_virtualenv(generator)

            self.assertEqual(environment["USER_VAR"], r"some value with space and \ (backslash)")
            self.assertEqual(environment["ANOTHER"], "data")

    @pytest.mark.tool_conan
    def test_list_with_spaces(self):
        generator = VirtualEnvGenerator(ConanFileMock())
        self.assertIn("CFLAGS", VirtualEnvGenerator.append_with_spaces)
        self.assertIn("CL", VirtualEnvGenerator.append_with_spaces)
        generator.env = {"CFLAGS": ["-O2"],
                         "CL": ["-MD", "-DNDEBUG", "-O2", "-Ob2"]}

        _, environment = self._run_virtualenv(generator)

        extra_blank = " " if platform.system() == "Windows" else ""  # FIXME: Extra blank under Windows
        self.assertEqual(environment["CFLAGS"], "-O2" + extra_blank)
        self.assertEqual(environment["CL"], "-MD -DNDEBUG -O2 -Ob2" + extra_blank)

        with environment_append({"CFLAGS": "cflags", "CL": "cl"}):
            _, environment = self._run_virtualenv(generator)
            self.assertEqual(environment["CFLAGS"], "-O2 cflags")
            self.assertEqual(environment["CL"], "-MD -DNDEBUG -O2 -Ob2 cl")

    @pytest.mark.tool_conan
    def test_list_variable(self):
        self.assertIn("PATH", os.environ)
        existing_path = os.environ.get("PATH")
        # Avoid duplicates in the path
        existing_path = os.pathsep.join(OrderedDict.fromkeys(existing_path.split(os.pathsep)))

        generator = VirtualEnvGenerator(ConanFileMock())
        generator.env = {"PATH": [os.path.join(self.test_folder, "bin"), r'other\path']}

        _, environment = self._run_virtualenv(generator)

        self.assertEqual(environment["PATH"], os.pathsep.join([
            os.path.join(self.test_folder, "bin"),
            r'other\path',
            self.ori_path,
            existing_path
        ]))

    @pytest.mark.tool_conan
    def test_empty_undefined_list_variable(self):
        self.assertNotIn("WHATEVER", os.environ)

        generator = VirtualEnvGenerator(ConanFileMock())
        generator.env = {"WHATEVER": ["list", "other"]}

        _, environment = self._run_virtualenv(generator)

        # FIXME: extra separator in Windows
        extra_separator = os.pathsep if platform.system() == "Windows" else ""
        self.assertEqual(environment["WHATEVER"],
                         "{}{}{}{}".format("list", os.pathsep, "other", extra_separator))

    @pytest.mark.tool_conan
    @pytest.mark.skipif(platform.system() == "Windows",
                        reason="Windows doesn't make distinction between empty and undefined environment variables")
    def test_empty_defined_list_variable(self):
        self.assertNotIn("WHATEVER", os.environ)
        try:
            os.environ["WHATEVER"] = ""

            generator = VirtualEnvGenerator(ConanFileMock())
            generator.env = {"WHATEVER": ["list", "other"]}

            _, environment = self._run_virtualenv(generator)

            self.assertEqual(environment["WHATEVER"], "{}{}{}".format("list", os.pathsep, "other"))
        finally:
            del os.environ["WHATEVER"]

    @pytest.mark.tool_conan
    def test_find_program(self):
        # If we add the path, we should found the env/executable instead of ori/executable
        # Watch out! 'cmd' returns all the paths where the executable is found, so we need to
        #   take into account the first match (iterate in reverse order)
        generator = VirtualEnvGenerator(ConanFileMock())
        generator.env = {"PATH": [self.env_path], }

        stdout, environment = self._run_virtualenv(generator)

        cpaths = dict(l.split("=", 1) for l in reversed(stdout.splitlines()) if l.startswith("__conan_"))
        self.assertEqual(cpaths["__conan_pre_path__"], cpaths["__conan_post_path__"])
        self.assertEqual(cpaths["__conan_env_path__"], cpaths["__conan_post_path__"])

        epaths = dict(l.split("=", 1) for l in reversed(stdout.splitlines()) if l.startswith("__exec_"))
        self.assertEqual(epaths["__exec_pre_path__"], epaths["__exec_post_path__"])
        self.assertEqual(epaths["__exec_env_path__"], os.path.join(self.env_path, self.app))

        # With any other path, we keep finding the original one
        generator = VirtualEnvGenerator(ConanFileMock())
        generator.env = {"PATH": [os.path.join(self.test_folder, "wrong")], }

        stdout, environment = self._run_virtualenv(generator)
        epaths = dict(l.split("=", 1) for l in reversed(stdout.splitlines()) if l.startswith("__exec_"))
        self.assertEqual(epaths["__exec_pre_path__"], epaths["__exec_post_path__"])
        self.assertEqual(epaths["__exec_env_path__"], epaths["__exec_post_path__"])
