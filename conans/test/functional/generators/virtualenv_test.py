import os
import platform
import subprocess
import textwrap
import unittest
from collections import OrderedDict

import six
from parameterized.parameterized import parameterized_class

from conans.client.generators.virtualenv import VirtualEnvGenerator
from conans.client.tools import OSInfo, files as tools_files
from conans.client.tools.env import environment_append
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import GenConanfile
from conans.util.files import decode_text, load, save_files, to_file_bytes


class VirtualEnvGeneratorTestCase(GraphManagerTest):
    """ Check that the declared variables in the ConanFile reach the generator """

    base = textwrap.dedent("""
        import os
        from conans import ConanFile

        class BaseConan(ConanFile):
            name = "base"
            version = "0.1"

            def package_info(self):
                self.env_info.PATH.extend([os.path.join("basedir", "bin"), "samebin"])
                self.env_info.LD_LIBRARY_PATH.append(os.path.join("basedir", "lib"))
                self.env_info.BASE_VAR = "baseValue"
                self.env_info.SPECIAL_VAR = "baseValue"
                self.env_info.BASE_LIST = ["baseValue1", "baseValue2"]
                self.env_info.CPPFLAGS = ["-baseFlag1", "-baseFlag2"]
                self.env_info.BCKW_SLASH = r"base\\value"
    """)

    dummy = textwrap.dedent("""
        import os
        from conans import ConanFile

        class DummyConan(ConanFile):
            name = "dummy"
            version = "0.1"
            requires = "base/0.1"

            def package_info(self):
                self.env_info.PATH = [os.path.join("dummydir", "bin"),"samebin"]
                self.env_info.LD_LIBRARY_PATH.append(os.path.join("dummydir", "lib"))
                self.env_info.SPECIAL_VAR = "dummyValue"
                self.env_info.BASE_LIST = ["dummyValue1", "dummyValue2"]
                self.env_info.CPPFLAGS = ["-flag1", "-flag2"]
                self.env_info.BCKW_SLASH = r"dummy\\value"
    """)

    def test_conanfile(self):
        base_ref = ConanFileReference.loads("base/0.1")
        dummy_ref = ConanFileReference.loads("dummy/0.1")

        self._cache_recipe(base_ref, self.base)
        self._cache_recipe(dummy_ref, self.dummy)
        deps_graph = self.build_graph(GenConanfile().with_requirement(dummy_ref))
        generator = VirtualEnvGenerator(deps_graph.root.conanfile)

        self.assertEqual(generator.env["BASE_LIST"],
                         ['dummyValue1', 'dummyValue2', 'baseValue1', 'baseValue2'])
        self.assertEqual(generator.env["BASE_VAR"], 'baseValue')
        self.assertEqual(generator.env["BCKW_SLASH"], 'dummy\\value')
        self.assertEqual(generator.env["CPPFLAGS"], ['-flag1', '-flag2', '-baseFlag1', '-baseFlag2'])
        self.assertEqual(generator.env["LD_LIBRARY_PATH"],
                         [os.path.join("dummydir", "lib"), os.path.join("basedir", "lib")])
        self.assertEqual(generator.env["PATH"], [os.path.join("dummydir", "bin"),
                                                 os.path.join("basedir", "bin"), 'samebin'])
        self.assertEqual(generator.env["SPECIAL_VAR"], 'dummyValue')


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
        if platform.system() == "Darwin":
            env_after.pop(six.u("PS1"), None)  # TODO: FIXME: Needed for the test to pass
            env_after.pop("PS1", None)  # TODO: FIXME: Needed for the test to pass
        self.assertDictEqual(env_before, env_after)  # Environment restored correctly

        return stdout, _load_env_file(os.path.join(self.test_folder, self.env_activated))

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

    def test_list_with_spaces(self):
        generator = VirtualEnvGenerator(ConanFileMock())
        self.assertIn("CFLAGS", VirtualEnvGenerator.append_with_spaces)
        self.assertIn("CL", VirtualEnvGenerator.append_with_spaces)
        generator.env = {"CFLAGS": ["-O2"],
                         "CL": ["-MD", "-DNDEBUG", "-O2", "-Ob2"]}

        _, environment = self._run_virtualenv(generator)

        self.assertEqual(environment["CFLAGS"], "-O2 ")  # FIXME: Trailing blank
        self.assertEqual(environment["CL"], "-MD -DNDEBUG -O2 -Ob2 ")  # FIXME: Trailing blank

        with environment_append({"CFLAGS": "cflags", "CL": "cl"}):
            _, environment = self._run_virtualenv(generator)
            extra_blank = " " if platform.system() != "Windows" else ""  # FIXME: Extra blank
            self.assertEqual(environment["CFLAGS"], "-O2 {}cflags".format(extra_blank))
            self.assertEqual(environment["CL"], "-MD -DNDEBUG -O2 -Ob2 {}cl".format(extra_blank))

    def test_list_variable(self):
        self.assertNotIn("WHATEVER", os.environ)
        self.assertIn("PATH", os.environ)
        existing_path = os.environ.get("PATH")
        # Avoid duplicates in the path
        existing_path = os.pathsep.join(OrderedDict.fromkeys(existing_path.split(os.pathsep)))

        generator = VirtualEnvGenerator(ConanFileMock())
        generator.env = {"PATH": [os.path.join(self.test_folder, "bin"), r'other\path'],
                         "WHATEVER": ["list", "other"]}

        _, environment = self._run_virtualenv(generator)

        self.assertEqual(environment["PATH"], os.pathsep.join([
            os.path.join(self.test_folder, "bin"),
            r'other\path',
            self.ori_path,
            existing_path
        ]))
        # FIXME: extra separator in Windows
        extra_separator = os.pathsep if platform.system() == "Windows" else ""
        self.assertEqual(environment["WHATEVER"],
                         "{}{}{}{}".format("list", os.pathsep, "other", extra_separator))

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
