import unittest

import six

from conans.errors import ConanException
from conans.model.settings import Settings, bad_value_msg, undefined_field, undefined_value


class SettingsLoadsTest(unittest.TestCase):

    def test_none_value(self):
        yml = "os: [None, Windows]"
        settings = Settings.loads(yml)
        # Same sha as if settings were empty
        self.assertEqual(settings.values.sha, Settings.loads("").values.sha)
        settings.validate()
        self.assertTrue(settings.os == None)
        self.assertEqual("", settings.values.dumps())
        settings.os = "None"
        self.assertEqual(settings.values.sha, Settings.loads("").values.sha)
        settings.validate()
        self.assertTrue(settings.os == "None")
        self.assertEqual("os=None", settings.values.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os == "Windows")
        self.assertEqual("os=Windows", settings.values.dumps())

    def test_any(self):
        yml = "os: ANY"
        settings = Settings.loads(yml)
        with six.assertRaisesRegex(self, ConanException, "'settings.os' value not defined"):
            settings.validate()  # Raise exception if unset
        settings.os = "None"
        settings.validate()
        self.assertTrue(settings.os == "None")
        self.assertEqual("os=None", settings.values.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os == "Windows")
        self.assertEqual("os=Windows", settings.values.dumps())

    def test_none_any(self):
        yml = "os: [None, ANY]"
        settings = Settings.loads(yml)
        settings.validate()
        settings.os = "None"
        settings.validate()
        self.assertTrue(settings.os == "None")
        self.assertEqual("os=None", settings.values.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os == "Windows")
        self.assertEqual("os=Windows", settings.values.dumps())

    def test_windows_linux_remove(self):
        yml = "os: [Windows, Linux]"
        settings = Settings.loads(yml)
        settings.os = "Windows"
        settings.os.remove("Linux")
        # removing a definition which is not contained shall not raise an exception
        settings.os.remove("invalid")
        settings.os.remove("ANY")
        with six.assertRaisesRegex(self, ConanException, "Invalid setting 'Windows'"):
            settings.os.remove("Windows")

    def test_none_any_remove(self):
        yml = "os: [None, ANY]"
        settings = Settings.loads(yml)
        settings.os = "Windows"
        # removing a definition which is not contained shall not raise an exception
        settings.os.remove("invalid")
        with six.assertRaisesRegex(self, ConanException, "Invalid setting 'Windows'"):
            settings.os.remove("ANY")

        settings = Settings.loads(yml)
        settings.os = "None"
        settings.os.remove("ANY")  # "None" is still valid
        with six.assertRaisesRegex(self, ConanException, "Invalid setting 'None'"):
            settings.os.remove("None")  # "None" is not valid anymore

    def test_any_remove(self):
        yml = "os: ANY"
        settings = Settings.loads(yml)
        settings.os = "Windows"
        # removing a definition which is not contained shall not raise an exception
        settings.os.remove("invalid")
        with six.assertRaisesRegex(self, ConanException, "Invalid setting 'Windows'"):
            settings.os.remove("ANY")

    def test_getattr_none(self):
        yml = "os: [None, Windows]"
        settings = Settings.loads(yml)
        self.assertEqual(settings.os, None)
        _os = getattr(settings, "os")
        self.assertEqual(_os, None)
        self.assertEqual(str(_os), "None")

    def test_get_safe(self):
        yml = "os: [None, Windows]"
        settings = Settings.loads(yml)
        settings.os = "Windows"
        self.assertEqual(settings.os, "Windows")
        self.assertEqual(settings.get_safe("compiler.version"), None)
        self.assertEqual(settings.get_safe("build_type"), None)
        self.assertEqual("Release", settings.get_safe("build_type", "Release"))
        self.assertEqual(False, settings.get_safe("build_type", False))
        self.assertEqual("Windows", settings.get_safe("os", "Linux"))

    def test_none_subsetting(self):
        yml = """os:
    None:
    Windows:
        subsystem: [None, cygwin]
"""
        settings = Settings.loads(yml)
        # Same sha as if settings were empty
        self.assertEqual(settings.values.sha, Settings.loads("").values.sha)
        settings.validate()
        self.assertTrue(settings.os == None)
        self.assertEqual("", settings.values.dumps())
        settings.os = "None"
        self.assertEqual(settings.values.sha, Settings.loads("").values.sha)
        settings.validate()
        self.assertTrue(settings.os == "None")
        self.assertEqual("os=None", settings.values.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os.subsystem == None)
        self.assertEqual("os=Windows", settings.values.dumps())
        settings.os.subsystem = "cygwin"
        self.assertEqual("os=Windows\nos.subsystem=cygwin", settings.values.dumps())

    def test_none__sub_subsetting(self):
        yml = """os:
    None:
        subsystem: [None, cygwin]
    Windows:
"""
        with six.assertRaisesRegex(self, ConanException,
                                   "settings.yml: None setting can't have subsettings"):
            Settings.loads(yml)


class SettingsTest(unittest.TestCase):

    def setUp(self):
        data = {"compiler": {
                            "Visual Studio": {
                                             "version": ["10", "11", "12"],
                                             "runtime": ["MD", "MT"]},
                            "gcc": {
                                   "version": ["4.8", "4.9"],
                                   "arch": {"x86": {"speed": ["A", "B"]},
                                            "x64": {"speed": ["C", "D"]}}}
                                   },
                "os": ["Windows", "Linux"]}
        self.sut = Settings(data)

    def test_in_contains(self):
        self.sut.compiler = "Visual Studio"
        self.assertTrue("Visual" in self.sut.compiler)
        self.assertFalse("Visual" not in self.sut.compiler)

    def test_os_split(self):
        settings = Settings.loads("""os:
    Windows:
    Linux:
    Macos:
        version: [1, 2]
    Android:
""")
        other_settings = Settings.loads("os: [Windows, Linux]")
        settings.os = "Windows"
        other_settings.os = "Windows"
        self.assertEqual(settings.values.sha, other_settings.values.sha)

    def test_any(self):
        data = {"target": "ANY"}
        sut = Settings(data)
        sut.target = "native"
        self.assertTrue(sut.target == "native")

    def test_multi_os(self):
        settings = Settings.loads("""os:
            Windows:
            Linux:
                distro: [RH6, RH7]
            Macos:
                codename: [Mavericks, Yosemite]
        """)
        settings.os = "Windows"
        self.assertEqual(settings.os, "Windows")
        settings.os = "Linux"
        settings.os.distro = "RH6"
        self.assertTrue(settings.os.distro == "RH6")
        with self.assertRaises(ConanException):
            settings.os.distro = "Other"
        with self.assertRaises(ConanException):
            settings.os.codename = "Yosemite"
        settings.os = "Macos"
        settings.os.codename = "Yosemite"
        self.assertTrue(settings.os.codename == "Yosemite")

    def test_remove(self):
        self.sut.remove("compiler")
        self.sut.os = "Windows"
        self.sut.validate()
        self.assertEqual(self.sut.values.dumps(), "os=Windows")

    def test_remove_compiler(self):
        self.sut.compiler.remove("Visual Studio")
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler = "Visual Studio"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler", "Visual Studio", ["gcc"]))

    def test_remove_version(self):
        self.sut.compiler["Visual Studio"].version.remove("12")
        self.sut.compiler = "Visual Studio"
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.version = "12"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler.version", "12", ["10", "11"]))
        self.sut.compiler.version = 11
        self.assertEqual(self.sut.compiler.version, "11")

    def test_remove_os(self):
        self.sut.os.remove("Windows")
        with self.assertRaises(ConanException) as cm:
            self.sut.os = "Windows"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.os", "Windows", ["Linux"]))
        self.sut.os = "Linux"
        self.assertEqual(self.sut.os, "Linux")

    def test_loads_default(self):
        settings = Settings.loads("""os: [Windows, Linux, Macos, Android, FreeBSD, SunOS]
arch: [x86, x86_64, arm]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
    gcc:
        version: ["4.8", "4.9", "5.0"]
    Visual Studio:
        runtime: [None, MD, MT, MTd, MDd]
        version: ["10", "11", "12"]
    clang:
        version: ["3.5", "3.6", "3.7"]

build_type: [None, Debug, Release]""")
        settings.compiler = "clang"
        settings.compiler.version = "3.5"
        self.assertEqual(settings.compiler, "clang")
        self.assertEqual(settings.compiler.version, "3.5")

    def test_loads(self):
        settings = Settings.loads("""
compiler:
    Visual Studio:
        runtime: [MD, MT]
        version:
            '10':
                arch: ["32"]
            '11':
                &id1
                arch: ["32", "64"]
            '12':
                *id1
    gcc:
        arch:
            x64:
                speed: [C, D]
            x86:
                speed: [A, B]
        version: ['4.8', '4.9']
os: [Windows, Linux]
""")
        settings.update_values([('compiler', 'Visual Studio'),
                                ('compiler.version', '10'),
                                ('compiler.version.arch', '32')])
        self.assertEqual(settings.values_list,
                         [('compiler', 'Visual Studio'),
                          ('compiler.version', '10'),
                          ('compiler.version.arch', '32')])

        settings.compiler.version = "10"
        settings.compiler.version.arch = "32"
        settings.compiler.version = "11"
        settings.compiler.version.arch = "64"
        settings.compiler.version = "12"
        settings.compiler.version.arch = "64"

        self.assertEqual(settings.values_list,
                         [('compiler', 'Visual Studio'),
                          ('compiler.version', '12'),
                          ('compiler.version.arch', '64')])

    def test_set_value(self):
        self.sut.update_values([("compiler", "Visual Studio")])
        self.assertEqual(self.sut.compiler, "Visual Studio")
        self.sut.update_values([("compiler.version", "12")])
        self.assertEqual(self.sut.compiler.version, "12")
        self.sut.update_values([("compiler", "gcc")])
        self.assertEqual(self.sut.compiler, "gcc")
        self.sut.update_values([("compiler.version", "4.8")])
        self.assertEqual(self.sut.compiler.version, "4.8")
        self.sut.update_values([("compiler.arch", "x86")])
        self.assertEqual(self.sut.compiler.arch, "x86")
        self.sut.update_values([("compiler.arch.speed", "A")])
        self.assertEqual(self.sut.compiler.arch.speed, "A")

    def test_constraint(self):
        s2 = {"os": None}
        self.sut.constraint(s2)
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler
        self.assertEqual(str(cm.exception), str(undefined_field("settings", "compiler", ["os"])))
        self.sut.os = "Windows"
        self.sut.os = "Linux"

    def test_constraint2(self):
        s2 = {"os2": None}
        with self.assertRaises(ConanException) as cm:
            self.sut.constraint(s2)
        self.assertEqual(str(cm.exception),
                         str(undefined_field("settings", "os2", ["compiler", "os"])))

    def test_constraint3(self):
        s2 = {"os": ["Win"]}
        with self.assertRaises(ConanException) as cm:
            self.sut.constraint(s2)
        self.assertEqual(str(cm.exception),
                         bad_value_msg("os", "Win", ["Windows", "Linux"]))

    def test_constraint4(self):
        s2 = {"os": ["Windows"]}
        self.sut.constraint(s2)
        with self.assertRaises(ConanException) as cm:
            self.sut.os = "Linux"
        self.assertEqual(str(cm.exception), bad_value_msg("settings.os", "Linux", ["Windows"]))

        self.sut.os = "Windows"

    def test_constraint5(self):
        s2 = {"os": None,
              "compiler": {"Visual Studio": {"version2": None}}}

        with self.assertRaises(ConanException) as cm:
            self.sut.constraint(s2)
        self.assertEqual(str(cm.exception), str(undefined_field("settings.compiler", "version2",
                                                                ['runtime', 'version'])))
        self.sut.os = "Windows"

    def test_constraint6(self):
        s2 = {"os": None,
              "compiler": {"Visual Studio": {"version": None}}}
        self.sut.constraint(s2)
        self.sut.compiler = "Visual Studio"
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.arch
        self.assertEqual(str(cm.exception), str(undefined_field("settings.compiler", "arch",
                                                                ['version'], "Visual Studio")))
        self.sut.os = "Windows"
        self.sut.compiler.version = "11"
        self.sut.compiler.version = "12"

    def test_constraint7(self):
        s2 = {"os": None,
              "compiler": {"Visual Studio": {"version": ("11", "10")},
                           "gcc": None}}

        self.sut.constraint(s2)
        self.sut.compiler = "Visual Studio"
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.version = "12"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler.version", "12", ["10", "11"]))
        self.sut.compiler.version = "10"
        self.sut.compiler.version = "11"
        self.sut.os = "Windows"
        self.sut.compiler = "gcc"

    def test_validate(self):
        with six.assertRaisesRegex(self, ConanException, str(undefined_value("settings.compiler"))):
            self.sut.validate()

        self.sut.compiler = "gcc"
        with six.assertRaisesRegex(self, ConanException,
                                   str(undefined_value("settings.compiler.arch"))):
            self.sut.validate()

        self.sut.compiler.arch = "x86"
        with six.assertRaisesRegex(self, ConanException,
                                   str(undefined_value("settings.compiler.arch.speed"))):
            self.sut.validate()

        self.sut.compiler.arch.speed = "A"
        with six.assertRaisesRegex(self, ConanException,
                                   str(undefined_value("settings.compiler.version"))):
            self.sut.validate()

        self.sut.compiler.version = "4.8"
        with six.assertRaisesRegex(self, ConanException, str(undefined_value("settings.os"))):
            self.sut.validate()

        self.sut.os = "Windows"
        self.sut.validate()
        self.assertEqual(self.sut.values_list, [("compiler", "gcc"),
                                                ("compiler.arch", "x86"),
                                                ("compiler.arch.speed", "A"),
                                                ("compiler.version", "4.8"),
                                                ("os", "Windows")])

    def test_validate2(self):
        self.sut.os = "Windows"
        self.sut.compiler = "Visual Studio"
        with six.assertRaisesRegex(self, ConanException,
                                   str(undefined_value("settings.compiler.runtime"))):
            self.sut.validate()

        self.sut.compiler.runtime = "MD"
        with six.assertRaisesRegex(self, ConanException,
                                   str(undefined_value("settings.compiler.version"))):
            self.sut.validate()

        self.sut.compiler.version = "10"
        self.sut.validate()

        self.assertEqual(self.sut.values_list, [("compiler", "Visual Studio"),
                                                ("compiler.runtime", "MD"),
                                                ("compiler.version", "10"),
                                                ("os", "Windows")])

    def test_basic(self):
        s = Settings({"os": ["Windows", "Linux"]})
        s.os = "Windows"
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler = "kk"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler", "kk", "['Visual Studio', 'gcc']"))

    def test_my(self):
        self.assertEqual(self.sut.compiler, None)

        with self.assertRaises(ConanException) as cm:
            self.sut.compiler = "kk"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler", "kk", "['Visual Studio', 'gcc']"))

        self.sut.compiler = "Visual Studio"
        self.assertEqual(str(self.sut.compiler), "Visual Studio")
        self.assertEqual(self.sut.compiler, "Visual Studio")

        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.kk
        self.assertEqual(str(cm.exception),
                         str(undefined_field("settings.compiler", "kk", "['runtime', 'version']",
                                             "Visual Studio")))

        self.assertEqual(self.sut.compiler.version, None)

        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.version = "123"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler.version", "123", ['10', '11', '12']))

        self.sut.compiler.version = "12"
        self.assertEqual(self.sut.compiler.version, "12")
        self.assertEqual(str(self.sut.compiler.version), "12")

        with self.assertRaises(ConanException) as cm:
            assert self.sut.compiler == "kk"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler", "kk", "['Visual Studio', 'gcc']"))

        self.assertFalse(self.sut.compiler == "gcc")
        self.assertTrue(self.sut.compiler == "Visual Studio")

        self.assertTrue(self.sut.compiler.version == "12")
        self.assertFalse(self.sut.compiler.version == "11")

        with self.assertRaises(ConanException) as cm:
            assert self.sut.compiler.version == "13"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler.version", "13", ['10', '11', '12']))

        self.sut.compiler = "gcc"
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.runtime
        self.assertEqual(str(cm.exception),
                         str(undefined_field("settings.compiler", "runtime", "['arch', 'version']",
                                             "gcc")))

        self.sut.compiler.arch = "x86"
        self.sut.compiler.arch.speed = "A"
        self.assertEqual(self.sut.compiler.arch.speed, "A")

        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.arch.speed = "D"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler.arch.speed", "D", ['A', 'B']))

        self.sut.compiler.arch = "x64"
        self.sut.compiler.arch.speed = "C"
        self.assertEqual(self.sut.compiler.arch.speed, "C")

        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.arch.speed = "A"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler.arch.speed", "A", ['C', 'D']))

        self.sut.compiler.arch.speed = "D"
        self.assertEqual(self.sut.compiler.arch.speed, "D")
