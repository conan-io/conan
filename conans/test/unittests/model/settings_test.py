import unittest

from conans.errors import ConanException
from conans.model.settings import Settings, bad_value_msg, undefined_field


def undefined_value(v):
    return "'%s' value not defined" % v


class SettingsLoadsTest(unittest.TestCase):

    def test_none_value(self):
        yml = "os: [None, Windows]"
        settings = Settings.loads(yml)
        # Same sha as if settings were empty
        self.assertEqual(settings.sha, Settings.loads("").sha)
        settings.validate()
        self.assertTrue(settings.os == None)
        self.assertEqual("", settings.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os == "Windows")
        self.assertEqual("os=Windows", settings.dumps())

    def test_any(self):
        yml = "os: [ANY]"
        settings = Settings.loads(yml)
        with self.assertRaisesRegex(ConanException, "'settings.os' value not defined"):
            settings.validate()  # Raise exception if unset
        settings.os = "some-os"
        settings.validate()
        self.assertTrue(settings.os == "some-os")
        self.assertIn("os=some-os", settings.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os == "Windows")
        self.assertEqual("os=Windows", settings.dumps())

    def test_none_any(self):
        yml = "os: [None, ANY]"
        settings = Settings.loads(yml)
        settings.validate()
        settings.os = "None"
        settings.validate()
        self.assertTrue(settings.os == "None")
        self.assertIn("os=None", settings.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os == "Windows")
        self.assertEqual("os=Windows", settings.dumps())

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
        self.assertEqual(settings.sha, Settings.loads("").sha)
        settings.validate()
        self.assertTrue(settings.os == None)
        self.assertEqual("", settings.dumps())
        settings.os = "Windows"
        self.assertTrue(settings.os.subsystem == None)
        self.assertEqual("os=Windows", settings.dumps())
        settings.os.subsystem = "cygwin"
        self.assertEqual("os=Windows\nos.subsystem=cygwin", settings.dumps())

    def test_none__sub_subsetting(self):
        yml = """os:
    None:
        subsystem: [None, cygwin]
    Windows:
"""
        with self.assertRaisesRegex(ConanException,
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
        self.assertEqual(settings.sha, other_settings.sha)

    def test_any(self):
        data = {"target": ["ANY"]}
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
        del self.sut.compiler
        self.sut.os = "Windows"
        self.sut.validate()
        self.assertEqual(self.sut.dumps(), "os=Windows")

    def test_loads_default(self):
        settings = Settings.loads("""os: [Windows, Linux, Macos, Android, FreeBSD, SunOS]
arch: [x86, x86_64, arm]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
    gcc:
        version: ["4.8", "4.9", "5.0"]
    msvc:
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
    msvc:
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
        settings.update_values([('compiler', 'msvc'),
                                ('compiler.version', '10'),
                                ('compiler.version.arch', '32')])
        self.assertEqual(settings.values_list,
                         [('compiler', 'msvc'),
                          ('compiler.version', '10'),
                          ('compiler.version.arch', '32')])

        settings.compiler.version = "10"
        settings.compiler.version.arch = "32"
        settings.compiler.version = "11"
        settings.compiler.version.arch = "64"
        settings.compiler.version = "12"
        settings.compiler.version.arch = "64"

        self.assertEqual(settings.values_list,
                         [('compiler', 'msvc'),
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
        s2 = ["os"]
        self.sut.constrained(s2)
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler
        self.assertEqual(str(cm.exception),
                         str(undefined_field("settings", "compiler", ["os"], "settings")))
        self.sut.os = "Windows"
        self.sut.os = "Linux"

    def test_constraint2(self):
        s2 = ["os2"]
        with self.assertRaises(ConanException) as cm:
            self.sut.constrained(s2)
        self.assertEqual(str(cm.exception),
                         str(undefined_field("settings", "os2", ["compiler", "os"], "settings")))

    def test_constraint6(self):
        s2 = {"os", "compiler"}
        self.sut.constrained(s2)
        self.sut.compiler = "Visual Studio"
        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.arch
        self.assertEqual(str(cm.exception), str(undefined_field("settings.compiler", "arch",
                                                                ['runtime', 'version'], "Visual Studio")))
        self.sut.os = "Windows"
        self.sut.compiler.version = "11"
        self.sut.compiler.version = "12"

    def test_validate(self):
        with self.assertRaisesRegex(ConanException, str(undefined_value("settings.compiler"))):
            self.sut.validate()

        self.sut.compiler = "gcc"
        with self.assertRaisesRegex(ConanException, "value not defined"):
            self.sut.validate()

        self.sut.compiler.arch = "x86"
        with self.assertRaisesRegex(ConanException, "value not defined"):
            self.sut.validate()

        self.sut.compiler.arch.speed = "A"
        with self.assertRaisesRegex(ConanException, "value not defined"):
            self.sut.validate()

        self.sut.compiler.version = "4.8"
        with self.assertRaisesRegex(ConanException, "value not defined"):
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
        with self.assertRaisesRegex(ConanException, "value not defined"):
            self.sut.validate()

        self.sut.compiler.runtime = "MD"
        with self.assertRaisesRegex(ConanException, "value not defined"):
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
                         bad_value_msg("settings.compiler", "kk", ['Visual Studio', 'gcc']))

    def test_my(self):
        self.assertEqual(self.sut.compiler, None)

        with self.assertRaises(ConanException) as cm:
            self.sut.compiler = "kk"
        self.assertEqual(str(cm.exception),
                         bad_value_msg("settings.compiler", "kk", ['Visual Studio', 'gcc']))

        self.sut.compiler = "Visual Studio"
        self.assertEqual(str(self.sut.compiler), "Visual Studio")
        self.assertEqual(self.sut.compiler, "Visual Studio")

        with self.assertRaises(ConanException) as cm:
            self.sut.compiler.kk
        self.assertEqual(str(cm.exception),
                         str(undefined_field("settings.compiler", "kk", ['runtime', 'version'],
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
                         bad_value_msg("settings.compiler", "kk", ['Visual Studio', 'gcc']))

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
