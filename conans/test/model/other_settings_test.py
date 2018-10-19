import os
import unittest

from conans.util.files import save, load
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE, CONANINFO
from conans.model.info import ConanInfo
from conans.model.settings import undefined_value, bad_value_msg
from conans.model.ref import PackageReference


class SettingsTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def wrong_settings_test(self):
        settings = """os:
    None:
        subsystem: [None, msys]
"""
        client = TestClient()
        save(client.paths.settings_path, settings)
        save(client.paths.default_profile_path, "")
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler"
"""
        client.save({"conanfile.py": conanfile})
        error = client.run("create . Pkg/0.1@lasote/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: settings.yml: None setting can't have subsettings", client.out)

    def custom_settings_test(self):
        settings = """os:
    None:
    Windows:
        subsystem: [None, cygwin]
    Linux:
compiler: [gcc, visual]
"""
        client = TestClient()
        save(client.paths.settings_path, settings)
        save(client.paths.default_profile_path, "")
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler"
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing -s compiler=gcc")
        self.assertIn("544c1d8c53e9d269737e68e00ec66716171d2704", client.out)
        client.run("search Pkg/0.1@lasote/testing")
        self.assertNotIn("os: None", client.out)
        package_reference = PackageReference.loads("Pkg/0.1@lasote/testing:544c1d8c53e9d269737e68e00ec66716171d2704")
        info_path = os.path.join(client.paths.package(package_reference), CONANINFO)
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
        """ This test is to validate that after adding a new settings, that allows a None
    value, this None value does not modify exisisting packages SHAs
    """
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
        files = {"conanfile.py": file_content}
        client = TestClient()
        client.save(files)
        client.run("export . lasote/testing")
        save(client.paths.settings_path, prev_settings)
        client.client_cache.default_profile  # Generate the default
        conf = load(client.client_cache.default_profile_path)
        conf = conf.replace("build_type=Release", "")
        self.assertNotIn("build_type", conf)
        save(client.client_cache.default_profile_path, conf)

        client.run("install test/1.9@lasote/testing --build -s arch=x86_64 -s compiler=gcc "
                   "-s compiler.version=4.9 -s os=Windows -s compiler.libcxx=libstdc++")
        self.assertIn("390146894f59dda18c902ee25e649ef590140732", client.user_io.out)

        # Now the new one
        files = {"conanfile.py": file_content.replace('"arch"', '"arch", "build_type"')}
        client = TestClient()
        client.save(files)
        client.run("export . lasote/testing")

        client.run("install test/1.9@lasote/testing --build -s arch=x86_64 -s compiler=gcc "
                   "-s compiler.version=4.9 -s os=Windows -s build_type=None -s compiler.libcxx=libstdc++")
        self.assertIn("build_type", load(client.paths.settings_path))
        self.assertIn("390146894f59dda18c902ee25e649ef590140732", client.user_io.out)

    def settings_constraint_error_type_test(self):
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

    def settings_constraint_test(self):
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = {"compiler": {"gcc": {"version": ["7.1"]}}}
    def build(self):
        self.output.info("Compiler version!: %s" % self.settings.compiler.version)
    """
        test = """from conans import ConanFile
class Test(ConanFile):
    requires = "Hello/0.1@user/channel"
    def test(self):
        pass
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        default_profile = os.path.join(client.base_folder, ".conan/profiles/default")
        save(default_profile, "[settings]\ncompiler=gcc\ncompiler.version=6.3")
        error = client.run("create . user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Invalid setting '6.3' is not a valid 'settings.compiler.version'",
                      client.user_io.out)
        client.run("create . user/channel -s compiler=gcc -s compiler.version=7.1")
        self.assertIn("Hello/0.1@user/channel: Compiler version!: 7.1", client.user_io.out)
        self.assertIn("Hello/0.1@user/channel: Generating the package", client.user_io.out)

    def settings_as_a_str_test(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
"""
        self.client.save({CONANFILE: content})
        self.client.run("install . -s os=Windows --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.os, "Windows")

        self.client.run("install . -s os=Linux --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.os, "Linux")

    def settings_as_a_list_conanfile_test(self):
        """Declare settings as a list"""
        # Now with conanfile as a list
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os", "arch"
"""
        self.client.save({CONANFILE: content})
        self.client.run("install . -s os=Windows --build missing")
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.os,  "Windows")
        self.assertEquals(conan_info.settings.fields, ["arch", "os"])

    def settings_as_a_dict_conanfile_test(self):
        """Declare settings as a dict"""
        # Now with conanfile as a dict
        # XXX: this test only works on machines that default arch to "x86" or "x86_64" or "sparc" or "sparcv9"
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {"os": ["Windows"], "arch": ["x86", "x86_64", "sparc", "sparcv9"]}
"""
        self.client.save({CONANFILE: content})
        self.client.run("install . -s os=Windows --build missing")
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.os,  "Windows")
        self.assertEquals(conan_info.settings.fields, ["arch", "os"])

    def invalid_settings_test(self):
        '''Test wrong values and wrong constraints'''
        self.client.client_cache.default_profile
        default_conf = load(self.client.paths.default_profile_path)
        new_conf = default_conf.replace("\nos=", "\n# os=")
        save(self.client.paths.default_profile_path, new_conf)
        # MISSING VALUE FOR A SETTING
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os", "build_type"
"""

        self.client.save({CONANFILE: content})
        self.client.run("install . --build missing", ignore_error=True)
        self.assertIn(str(undefined_value("settings.os")), str(self.client.user_io.out))

    def invalid_settings_test2(self):
        # MISSING A DEFAULT VALUE BECAUSE ITS RESTRICTED TO OTHER, SO ITS REQUIRED
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {"os": ["Windows", "Linux", "Macos", "FreeBSD", "SunOS"], "compiler": ["Visual Studio"]}
"""

        self.client.save({CONANFILE: content})
        self.client.run("install . -s compiler=gcc -s compiler.version=4.8 --build missing", ignore_error=True)
        self.assertIn(bad_value_msg("settings.compiler", "gcc", ["Visual Studio"]),
                      str(self.client.user_io.out))

    def invalid_settings_test3(self):
        # dict without options
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {"os": None, "compiler": ["Visual Studio"]}
"""

        self.client.save({CONANFILE: content})
        self.client.run("install . -s compiler=gcc -s compiler.version=4.8 --build missing", ignore_error=True)
        self.assertIn(bad_value_msg("settings.compiler", "gcc", ["Visual Studio"]),
                      str(self.client.user_io.out))

        # Test wrong settings in conanfile
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = invalid
"""

        self.client.save({CONANFILE: content})
        self.client.run("install . --build missing", ignore_error=True)
        self.assertIn("invalid' is not defined",
                      str(self.client.user_io.out))

        # Test wrong values in conanfile
    def invalid_settings_test4(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
"""

        self.client.save({CONANFILE: content})
        self.client.run("install . -s os=ChromeOS --build missing", ignore_error=True)
        self.assertIn(bad_value_msg("settings.os", "ChromeOS",
                                    ['Android', 'Arduino', 'FreeBSD', 'Linux', 'Macos', 'SunOS', 'Windows',
                                     'WindowsStore', 'iOS', 'tvOS', 'watchOS']),
                      str(self.client.user_io.out))

        # Now add new settings to config and try again
        config = load(self.client.paths.settings_path)
        config = config.replace("Windows:%s" % os.linesep,
                                "Windows:%s    ChromeOS:%s" % (os.linesep, os.linesep))

        save(self.client.paths.settings_path, config)
        self.client.run("install . -s os=ChromeOS --build missing")
        self.assertIn('Generated conaninfo.txt', str(self.client.user_io.out))

        # Settings is None
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = None
"""
        self.client.save({CONANFILE: content})
        self.client.run("install . --build missing")
        self.assertIn('Generated conaninfo.txt', str(self.client.user_io.out))
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.dumps(), "")

        # Settings is {}
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = {}
"""
        self.client.save({CONANFILE: content})
        self.client.run("install . --build missing")
        self.assertIn('Generated conaninfo.txt', str(self.client.user_io.out))
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.dumps(), "")
