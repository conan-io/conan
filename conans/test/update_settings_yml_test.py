import unittest
from conans.test.tools import TestClient
from conans.util.files import load, save


class UpdateSettingsYmlTest(unittest.TestCase):
    """ This test is to validate that after adding a new settings, that allows a None
    value, this None value does not modify exisisting packages SHAs
    """

    def test_update_settings(self):
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
os: [Windows, Linux, Macos, Android, FreeBSD]
arch: [x86, x86_64, armv6, armv7, armv7hf, armv8]
compiler:
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
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.1", "7.2", "7.3"]
        libcxx: [libstdc++, libc++]

"""
        files = {"conanfile.py": file_content}
        client = TestClient()
        save(client.paths.settings_path, prev_settings)
        conf = load(client.paths.conan_conf_path)
        conf = conf.replace("build_type=Release", "")
        self.assertNotIn("build_type", conf)
        save(client.paths.conan_conf_path, conf)
        self.assertNotIn("build_type", client.paths.conan_config.settings_defaults.dumps())
        client.save(files)
        client.run("export lasote/testing")
        self.assertNotIn("build_type", load(client.paths.settings_path))
        self.assertNotIn("build_type", load(client.paths.conan_conf_path))
        self.assertNotIn("build_type", client.paths.conan_config.settings_defaults.dumps())

        client.run("install test/1.9@lasote/testing --build -s compiler=gcc "
                   "-s compiler.version=4.9 -s os=Windows -s compiler.libcxx=libstdc++")
        self.assertIn("390146894f59dda18c902ee25e649ef590140732", client.user_io.out)

        # Now the new one
        files = {"conanfile.py": file_content.replace('"arch"', '"arch", "build_type"')}
        client = TestClient()
        client.save(files)
        client.run("export lasote/testing")

        client.run("install test/1.9@lasote/testing --build -s compiler=gcc "
                   "-s compiler.version=4.9 -s os=Windows -s build_type=None -s compiler.libcxx=libstdc++")
        self.assertIn("build_type", load(client.paths.settings_path))
        self.assertIn("390146894f59dda18c902ee25e649ef590140732", client.user_io.out)
