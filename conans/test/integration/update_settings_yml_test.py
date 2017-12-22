import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load, save
from conans.client.conf import default_settings_yml
from conans.model.settings import Settings


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
