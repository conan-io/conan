import os
import textwrap
import unittest

from conans.model.info import ConanInfo
from conans.model.ref import PackageReference
from conans.model.settings import bad_value_msg, undefined_value
from conans.paths import CONANFILE, CONANINFO
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import load, save


class SettingsTest(unittest.TestCase):

    def test_wrong_settings(self):
        settings = """os:
    None:
        subsystem: [None, msys]
"""
        client = TestClient()
        save(client.cache.settings_path, settings)
        save(client.cache.default_profile_path, "")
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler"
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing", assert_error=True)
        self.assertIn("ERROR: settings.yml: None setting can't have subsettings", client.out)

    def test_custom_compiler_preprocessor(self):
        # https://github.com/conan-io/conan/issues/3842
        settings = """compiler:
    mycomp:
        version: ["2.3", "2.4"]
cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
"""
        client = TestClient()
        save(client.cache.settings_path, settings)
        save(client.cache.default_profile_path, """[settings]
compiler=mycomp
compiler.version=2.3
cppstd=11
""")
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "compiler", "cppstd"
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("""Configuration:
[settings]
compiler=mycomp
compiler.version=2.3
cppstd=11""", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: Package "
                      "'c2f0c2641722089d9b11cd646c47d239af044b5a' created",
                      client.out)

    def test_build_folder_vars(self):
        settings = textwrap.dedent("""\
            os:
                None:
                Windows:
                    subsystem: [None, cygwin]
                Linux:
            compiler: [gcc, visual]
            """)
        client = TestClient()
        save(client.cache.settings_path, settings)
        save(client.cache.default_profile_path, "")

        client.save({"conanfile.py": GenConanfile().with_settings("os", "compiler")})
        client.run("create . Pkg/0.1@lasote/testing -s compiler=gcc")
        self.assertIn("544c1d8c53e9d269737e68e00ec66716171d2704", client.out)
        client.run("search Pkg/0.1@lasote/testing")
        self.assertNotIn("os: None", client.out)
        pref = PackageReference.loads("Pkg/0.1@lasote/testing:"
                                      "544c1d8c53e9d269737e68e00ec66716171d2704")
        info_path = os.path.join(client.cache.package_layout(pref.ref).package(pref), CONANINFO)
        info = load(info_path)
        self.assertNotIn("os", info)
        # Explicitly specifying None, put it in the conaninfo.txt, but does not affect the hash
        client.run("create . Pkg/0.1@lasote/testing -s compiler=gcc -s os=None")
        self.assertIn("544c1d8c53e9d269737e68e00ec66716171d2704", client.out)
        client.run("search Pkg/0.1@lasote/testing")
        self.assertIn("os: None", client.out)
        info = load(info_path)
        self.assertIn("os", info)

    def test_update_settings(self):
        # This test is to validate that after adding a new settings, that allows a None
        # value, this None value does not modify exisisting packages SHAs
        file_content = '''
from conans import ConanFile

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9"
    settings = "os", "compiler", "arch"

    def source(self):
        self.output.warn("Sourcing...")

    def build(self):
        self.output.warn("Building...")
    '''
        prev_settings = """
os: [Windows, Linux, Macos, Android, FreeBSD, SunOS]
arch: [x86, x86_64, armv6, armv7, armv7hf, armv8, sparc, sparcv9]
os_build: [Windows, Linux, Macos, Android, FreeBSD, SunOS]
arch_build: [x86, x86_64, armv6, armv7, armv7hf, armv8, sparc, sparcv9]

compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
        libcxx: [libCstd, libstdcxx libstlport, libstdc++]
    gcc:
        version: ["4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3", "5.4", "6.1", "6.2", "6.3"]
        libcxx: [libstdc++, libstdc++11]
    Visual Studio:
        runtime: [None, MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.1", "7.2", "7.3", "8.0", "8.1"]
        libcxx: [libstdc++, libc++]

"""
        client = TestClient()
        client.save({"conanfile.py": file_content})
        client.run("export . lasote/testing")
        save(client.cache.settings_path, prev_settings)
        client.cache.default_profile  # Generate the default
        conf = load(client.cache.default_profile_path)
        conf = conf.replace("build_type=Release", "")
        self.assertNotIn("build_type", conf)
        save(client.cache.default_profile_path, conf)

        client.run("install test/1.9@lasote/testing --build -s arch=x86_64 -s compiler=gcc "
                   "-s compiler.version=4.9 -s os=Windows -s compiler.libcxx=libstdc++")
        self.assertIn("390146894f59dda18c902ee25e649ef590140732", client.out)

        # Now the new one
        files = {"conanfile.py": file_content.replace('"arch"', '"arch", "build_type"')}
        client = TestClient()
        client.save(files)
        client.run("export . lasote/testing")

        client.run("install test/1.9@lasote/testing --build -s arch=x86_64 -s compiler=gcc "
                   "-s compiler.version=4.9 -s os=Windows -s build_type=None -s "
                   "compiler.libcxx=libstdc++")
        self.assertIn("build_type", load(client.cache.settings_path))
        self.assertIn("390146894f59dda18c902ee25e649ef590140732", client.out)

    def test_settings_constraint_error_type(self):
        # https://github.com/conan-io/conan/issues/3022
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    settings = {"os": "Linux"}
    def build(self):
        self.output.info("OS!!: %s" % self.settings.os)
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing -s os=Linux")
        self.assertIn("Pkg/0.1@user/testing: OS!!: Linux", client.out)

    def test_settings_constraint(self):
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = {"compiler": {"gcc": {"version": ["7.1"]}}}
    def build(self):
        self.output.info("Compiler version!: %s" % self.settings.compiler.version)
    """
        test = GenConanfile().with_requires("Hello/0.1@user/channel").with_test("pass")
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        default_profile = os.path.join(client.cache_folder, "profiles/default")
        save(default_profile, "[settings]\ncompiler=gcc\ncompiler.version=6.3")
        client.run("create . user/channel", assert_error=True)
        self.assertIn("Invalid setting '6.3' is not a valid 'settings.compiler.version'",
                      client.out)
        client.run("create . user/channel -s compiler=gcc -s compiler.version=7.1")
        self.assertIn("Hello/0.1@user/channel: Compiler version!: 7.1", client.out)
        self.assertIn("Hello/0.1@user/channel: Generating the package", client.out)

    def test_settings_as_a_str(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("install . -s os=Windows --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = ConanInfo.loads(client.load(CONANINFO))
        self.assertEqual(conan_info.settings.os, "Windows")

        client.run("install . -s os=Linux --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = ConanInfo.loads(client.load(CONANINFO))
        self.assertEqual(conan_info.settings.os, "Linux")

    def test_settings_as_a_list_conanfile(self):
        # Now with conanfile as a list
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os", "arch"
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("install . -s os=Windows --build missing")
        conan_info = ConanInfo.loads(client.load(CONANINFO))
        self.assertEqual(conan_info.settings.os,  "Windows")
        self.assertEqual(conan_info.settings.fields, ["arch", "os"])

    def test_settings_as_a_dict_conanfile(self):
        # Now with conanfile as a dict
        # XXX: this test only works on machines w default arch "x86", "x86_64", "sparc" or "sparcv9"
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {"os": ["Windows"], "arch": ["x86", "x86_64", "sparc", "sparcv9"]}
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("install . -s os=Windows -s arch=x86_64 --build missing")
        conan_info = ConanInfo.loads(client.load(CONANINFO))
        self.assertEqual(conan_info.settings.os,  "Windows")
        self.assertEqual(conan_info.settings.fields, ["arch", "os"])

    def test_invalid_settings(self):
        # Test wrong values and wrong constraints
        client = TestClient()
        # MISSING VALUE FOR A SETTING
        client.save({CONANFILE: GenConanfile().with_settings("os", "build_type"),
                     "profile": "[settings]\nbuild_type=Release"})
        client.run("install . -pr=profile --build missing", assert_error=True)
        self.assertIn(str(undefined_value("settings.os")), str(client.out))

    def test_invalid_settings2(self):
        # MISSING A DEFAULT VALUE BECAUSE ITS RESTRICTED TO OTHER, SO ITS REQUIRED
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {"os": ["Windows", "Linux", "Macos", "FreeBSD", "SunOS"],
                "compiler": ["Visual Studio"]}
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("install . -s compiler=gcc -s compiler.version=4.8 --build missing",
                   assert_error=True)
        self.assertIn(bad_value_msg("settings.compiler", "gcc", ["Visual Studio"]),
                      str(client.out))

    def test_invalid_settings3(self):
        # dict without options
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {"os": None, "compiler": ["Visual Studio"]}
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("install . -s compiler=gcc -s compiler.version=4.8 --build missing",
                   assert_error=True)
        self.assertIn(bad_value_msg("settings.compiler", "gcc", ["Visual Studio"]),
                      str(client.out))

        # Test wrong settings in conanfile
        content = textwrap.dedent("""
            from conans import ConanFile

            class SayConan(ConanFile):
                settings = invalid
            """)

        client.save({CONANFILE: content})
        client.run("install . --build missing", assert_error=True)
        self.assertIn("invalid' is not defined", client.out)

        # Test wrong values in conanfile
    def test_invalid_settings4(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
"""
        client = TestClient()
        client.save({CONANFILE: content})
        client.run("install . -s os=ChromeOS --build missing", assert_error=True)
        self.assertIn(bad_value_msg("settings.os", "ChromeOS",
                                    ['AIX', 'Android', 'Arduino', 'Emscripten', 'FreeBSD', 'Linux', 'Macos', 'Neutrino',
                                     'SunOS', 'VxWorks', 'Windows', 'WindowsCE', 'WindowsStore', 'baremetal', 'iOS', 'tvOS',
                                     'watchOS']),
                      client.out)

        # Now add new settings to config and try again
        config = load(client.cache.settings_path)
        config = config.replace("Windows:%s" % os.linesep,
                                "Windows:%s    ChromeOS:%s" % (os.linesep, os.linesep))

        save(client.cache.settings_path, config)
        client.run("install . -s os=ChromeOS --build missing")
        self.assertIn('Generated conaninfo.txt', client.out)

        # Settings is None
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = None
"""
        client.save({CONANFILE: content})
        client.run("install . --build missing")
        self.assertIn('Generated conaninfo.txt', client.out)
        conan_info = ConanInfo.loads(client.load(CONANINFO))
        self.assertEqual(conan_info.settings.dumps(), "")

        # Settings is {}
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {}
"""
        client.save({CONANFILE: content})
        client.run("install . --build missing")
        self.assertIn('Generated conaninfo.txt', client.out)
        conan_info = ConanInfo.loads(client.load(CONANINFO))
        self.assertEqual(conan_info.settings.dumps(), "")
