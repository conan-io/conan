import unittest
from conans.test.tools import TestServer, TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.model.profile import Profile
from conans.util.files import save, load
import os


class ProfileTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def install_profile_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        files["conanfile.py"] = files["conanfile.py"].replace("generators =", "generators = \"txt\",")

        # Create a profile and use it
        profile_settings = {"compiler": "Visual Studio",
                            "compiler.version": "12",
                            "compiler.runtime": "MD",
                            "arch": "x86"}
        self._create_profile("vs_12_86", profile_settings)

        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install --build missing -pr vs_12_86")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        for setting, value in profile_settings.items():
            self.assertIn("%s=%s" % (setting, value), info)

        # Try to override some settings in install command
        self.client.run("install --build missing -pr vs_12_86 -s compiler.version=14")
        info = load(os.path.join(self.client.current_folder, "conaninfo.txt"))
        for setting, value in profile_settings.items():
            if setting != "compiler.version":
                self.assertIn("%s=%s" % (setting, value), info)
            else:
                self.assertIn("compiler.version=14", info)

    def _create_profile(self, name, settings):
        profile = Profile()
        profile.settings = settings
        save(self.client.client_cache.profile_path(name), profile.dumps())
