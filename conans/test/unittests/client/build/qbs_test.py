import unittest
import conans.client.build.qbs as qbs

from conans.client import tools
from conans.test.utils.mocks import ConanFileMock, MockSettings


class ConanFileMockWithMultipleCommands(ConanFileMock):
    def __init__(self):
        self.command = []

    def run(self, command):
        self.command.append(command)


class QbsTest(unittest.TestCase):
    def test_call_qbs_config_with_single_value(self):
        conanfile = ConanFileMock()
        profile_name = "my_fancy_profile"
        key = "test_key"
        value = "test_value"
        expected_key = "profiles.%s.%s" % (profile_name, key)
        expected_value = value
        qbs._qbs_config(conanfile, profile_name, value)
        self.assertEqual(conanfile.command,
                         "qbs-config --settings-dir %s %s %s" % (
                            conanfile.build_folder, expected_key,
                            expected_value))

    def test_split_env_var_into_list(self):
        expected_list = ['-p1', '-p2', '-p3_with_value=13',
                         '-p_with_space1="hello world"',
                         '"-p_with_space2=Hello World"']
        env_var = " ".join(expected_list)
        self.assertEqual(qbs._env_var_to_list(env_var), expected_list)

    def test_compiler_not_in_settings(self):
        conanfile = ConanFileMock()
        conanfile.settings = MockSettings()
        with self.assertRaises(qbs.QbsException):
            qbs._check_for_compiler(conanfile)

    def test_compiler_in_settings_not_supported(self):
        conanfile = ConanFileMock()
        conanfile.settings = MockSettings({"compiler":
                                           "not realy a compiler name"})
        with self.assertRaises(qbs.QbsException):
            qbs._check_for_compiler(conanfile)

    def test_valid_compiler(self):
        supported_compilers = ["Visual Studio", "gcc", "clang"]
        for compiler in supported_compilers:
            conanfile = ConanFileMock()
            conanfile.settings = MockSettings({"compiler": compiler})
            qbs._check_for_compiler(conanfile)

    @staticmethod
    def _settings_to_test_against(self):
        return [
            {"os": "Windows", "compiler": "gcc", "qbs_compiler": "mingw"},
            {"os": "Windows", "compiler": "clang",
             "qbs_compiler": "clang-cl"},
            {"os": "Windows", "compiler": "Visual Studio",
             "qbs_compiler": "cl"},
            {"os": "Windows", "compiler": "Visual Studio",
             "toolset": "ClangCl", "qbs_compiler": "clang-cl"},
            {"os": "Linux", "compiler": "gcc", "qbs_compiler": "gcc"},
            {"os": "Linux", "compiler": "clang", "qbs_compiler": "clang"}
        ]

    def test_convert_compiler_name_to_qbs_compiler_name(self):
        for settings in self._settings_to_test_against():
            def expected():
                return settings["qbs_compiler"]
            conanfile = ConanFileMock()
            conanfile.settings = settings
            self.assertEqual(qbs._compiler_name(conanfile), expected())

    def test_settings_dir_location(self):
        conanfile = ConanFileMock()
        self.assertEqual(qbs._settings_dir(conanfile), conanfile.build_folder)

    def test_setup_toolchain_without_any_env_values(self):
        stub_profile_name = "foobar"
        for settings in self._settings_to_test_against():
            conanfile = ConanFileMockWithMultipleCommands()
            conanfile.settings = settings
            qbs._setup_toolchain(conanfile, stub_profile_name)
            self.assertEqual(len(conanfile.command), 1)
            self.assertEqual(
                conanfile.command[0],
                "qbs-setup-toolchains --settings-dir %s %s %s" % (
                    conanfile.build_folder, settings["qbs_compiler"],
                    stub_profile_name))

    def test_setup_toolchain_with_compiler_from_env(self):
        compiler = "compiler_from_env"
        stub_profile_name = "foobar"
        for settings in self._settings_to_test_against():
            conanfile = ConanFileMockWithMultipleCommands()
            conanfile.settings = settings
            with tools.environment_append({"CC": compiler}):
                qbs._setup_toolchain(conanfile, stub_profile_name)
            self.assertEqual(len(conanfile.command), 1)
            self.assertEqual(
                conanfile.command[0],
                "qbs-setup-toolchains --settings-dir %s %s %s" % (
                    conanfile.build_folder, compiler,
                    stub_profile_name))

    @staticmethod
    def _generate_flags(flag, qbs_key):
        return {"env": ('-{0}1 -{0}2 -{0}3_with_value=13 '
                        '-{0}_with_space1="hello world" '
                        '"-{0}_with_space2=Hello World"').format(flag),
                "qbs_value": ('["-{0}1", "-{0}2", "-{0}3_with_value=13", '
                              '"-{0}_with_space1=hello world", '
                              '"-{0}_with_space2=Hello World"').format(flag),
                "qbs_key": qbs_key}

    def test_setup_toolchain_with_flags_from_env(self):
        stub_profile_name = "foobar"
        conanfile = ConanFileMockWithMultipleCommands()
        compiler = "gcc"
        conanfile.settings = {"os": "Linux", "compiler": compiler}

        asm = self._generate_flags("asm", "assemblerFlags")
        c = self._generate_flags("c", "cFlags")
        cpp = self._generate_flags("cpp", "cppFlags")
        cxx = self._generate_flags("cxx", "cxxFlags")
        wl = self._generate_flags("Wl,", "linkerFlags")
        ld = self._generate_flags("ld", "linkerFlags")
        env = {
            "ASFLAGS": asm["env"],
            "CFLAGS": c["env"],
            "CPPFLAGS": cpp["env"],
            "CXXFLAGS": cxx["env"],
            "LDFLAGS": wl["env"] + "-Wl," + ld["env"].replace(" -", ",-")
        }
        with tools.environment_append(env):
            qbs._setup_toolchain(conanfile, stub_profile_name)
        self.assertEqual(len(conanfile.command), 1 + len(env))
        self.assertEqual(
            conanfile.command[0],
            "qbs-setup-toolchains --settings-dir %s %s %s" % (
                conanfile.build_folder, compiler,
                stub_profile_name))

        qbs_config = [
            {"key": asm["qbs_key"], "value": asm["qbs_value"]},
            {"key": c["qbs_key"], "value": c["qbs_value"]},
            {"key": cpp["qbs_key"], "value": cpp["qbs_value"]},
            {"key": cxx["qbs_key"], "value": cxx["qbs_value"]},
            {"key": wl["qbs_key"],
             "value": (wl["qbs_value"] +
                       ld["qbs_values"]).replace("][", ", ", 1)},
        ]
        self.assertEqual(len(conanfile.command)-1, len(qbs_config))
        for i in range(len(qbs_config)):
            item = qbs_config[i]
            key = "profiles.%s.%s" % (stub_profile_name, item["key"])
            self.assertEqual(
                conanfile.command[i+1],
                "qbs-config --settings-dir %s %s. %s" % (
                    conanfile.build_folder, key, item["value"]))

    def test_generating_config_command_line(self):
        name = "default"
        dict = {
            "modules.cpp.cxxFlags": ["-frtti", "-fexceptions"],
            "modules.cpp.ldFlags": "--defsym=hello_world",
            "products.App.myIntProperty": 13,
            "products.App.myBoolProperty": True
        }
        self.assetEqual(
            qbs._configuration_dict_to_commandlist(name, dict),
            'config:%s %s:["%s"] %s:"%s" %s:%s %s:%s' % (
                name,
                "modules.cpp.cxxFlags",
                '", "'.join(dict["modules.cpp.cxxFlags"]),
                "modules.cpp.ldFlags",
                dict["modules.cpp.ldFlags"],
                "products.App.myIntProperty",
                dict["products.App.myIntProperty"],
                "products.App.myBoolProperty", "true"))

    def test_construct_build_helper_without_project_file(self):
        conanfile = ConanFileMock()
        conanfile.settings = {"os": "Linux", "compiler": "gcc"}
        build_helper = qbs.Qbs(conanfile)
        self.assertEqual(build_helper.jobs, tools.cpu_count())
        self.assertEqual(build_helper._project_file, conanfile.source_folder)

    def test_construct_build_helper_with_project_file(self):
        conanfile = ConanFileMock()
        conanfile.settings = {"os": "Linux", "compiler": "gcc"}
        build_helper = qbs.Qbs(conanfile, project_file=conanfile.source_folder)
        self.assertEqual(build_helper._project_file, conanfile.source_folder)

    def test_construct_build_helper_with_wrong_project_file_path(self):
        conanfile = ConanFileMock()
        conanfile.settings = {"os": "Linux", "compiler": "gcc"}
        with self.assertRaises(qbs.QbsException):
            qbs.Qbs(conanfile, project_file="random/file/path")

    def test_setup_profile(self):
        conanfile = ConanFileMockWithMultipleCommands()
        conanfile.settings = {"os": "Linux", "compiler": "gcc"}
        build_helper = qbs.Qbs(conanfile)

        conanfile.command = []
        stub_profile_name = "stub_profile"
        base_profile_name = build_helper._base_profile_name
        key = "testKey"
        value = "testValue"
        expected_key = "profiles.%s.%s" % (stub_profile_name, key)
        build_helper.setup_profile(stub_profile_name, {key, value})
        self.assertEqual(len(conanfile.command), 2)
        self.assertEqual(
            conanfile.command[0],
            "qbs-config --settings-dir . %s profiles.%s.baseProfile %s" % (
                conanfile.build_folder, stub_profile_name, base_profile_name))
        self.assertEqual(
            conanfile.command[1],
            "qbs-config --settings-dir . %s %s %s" % (
                conanfile.build_folder, expected_key, value))

    def test_add_configuration(self):
        conanfile = ConanFileMock()
        conanfile.settings = {"os": "Linux", "compiler": "gcc"}
        build_helper = qbs.Qbs(conanfile)
        configurations = [
            {"name": "debug",
             "values": {"modules.cpp.cxxFlags": ["-frtti", "-fexceptions"]}},
            {"name": "release",
             "values": {"modules.cpp.cxxFlags": ["-fno-exceptions",
                                                 "-fno-rtti"]}}
        ]
        for config in configurations:
            build_helper.add_configuration(config["name"], config["values"])
        self.assertEqual(build_helper._configuration, configurations)

    def test_build(self):
        conanfile = ConanFileMock()
        conanfile.settings = {"os": "Linux", "compiler": "gcc"}
        build_helper = qbs.Qbs(conanfile)

        self.assertEqual(
            conanfile.command,
            ("qbs build --no-install --settings-dir %s --build-directory %s "
             "--file %s --jobs %s profile:%s") % (
                conanfile.build_folder,
                conanfile.build_folder, build_helper._project_file,
                build_helper.jobs, build_helper._base_profile_name))

    def test_build_with_custom_configuration(self):
        conanfile = ConanFileMock()
        conanfile.settings = {"os": "Linux", "compiler": "gcc"}
        build_helper = qbs.Qbs(conanfile)
        config_name = "debug"
        config_values = {"product.App.customProperty": []}
        build_helper.add_configuration(config_name, config_values)
