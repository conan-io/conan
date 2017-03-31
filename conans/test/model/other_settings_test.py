import unittest
from conans.util.files import save, load
from conans.test.utils.tools import TestClient
from conans.paths import CONANFILE, CONANINFO
from conans.model.info import ConanInfo
import os
from conans.model.settings import undefined_value, bad_value_msg


class SettingsTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def settings_as_a_str_test(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
"""
        self.client.save({CONANFILE: content})
        self.client.run("install -s os=Windows --build missing")
        # Now read the conaninfo and verify that settings applied is only os and value is windows
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.os, "Windows")

        self.client.run("install -s os=Linux --build missing")
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
        self.client.run("install -s os=Windows --build missing")
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
        self.client.run("install -s os=Windows --build missing")
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.os,  "Windows")
        self.assertEquals(conan_info.settings.fields, ["arch", "os"])

    def invalid_settings_test(self):
        '''Test wrong values and wrong constraints'''
        default_conf = load(self.client.paths.conan_conf_path)
        new_conf = default_conf.replace("os=", "# os=")
        save(self.client.paths.conan_conf_path, new_conf)
        # MISSING VALUE FOR A SETTING
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os", "build_type"
"""

        self.client.save({CONANFILE: content})
        self.client.run("install --build missing", ignore_error=True)
        self.assertIn(undefined_value("settings.os"), str(self.client.user_io.out))

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
        self.client.run("install -s compiler=gcc -s compiler.version=4.8 --build missing", ignore_error=True)
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
        self.client.run("install -s compiler=gcc -s compiler.version=4.8 --build missing", ignore_error=True)
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
        self.client.run("install --build missing", ignore_error=True)
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
        self.client.run("install -s os=ChromeOS --build missing", ignore_error=True)
        self.assertIn(bad_value_msg("settings.os", "ChromeOS",
                                    ['Android', 'FreeBSD', 'Linux', 'Macos', 'SunOS', 'Windows', 'iOS']),
                      str(self.client.user_io.out))

        # Now add new settings to config and try again
        config = load(self.client.paths.settings_path)
        config = config.replace("Windows:%s" % os.linesep,
                                "Windows:%s    ChromeOS:%s" % (os.linesep, os.linesep))

        save(self.client.paths.settings_path, config)
        self.client.run("install -s os=ChromeOS --build missing")
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
        self.client.run("install --build missing")
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
        self.client.run("install --build missing")
        self.assertIn('Generated conaninfo.txt', str(self.client.user_io.out))
        conan_info = ConanInfo.loads(load(os.path.join(self.client.current_folder, CONANINFO)))
        self.assertEquals(conan_info.settings.dumps(), "")
