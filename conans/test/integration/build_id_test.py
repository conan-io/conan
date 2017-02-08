import unittest
from conans.test.tools import TestClient
import os
from conans.util.files import load


conanfile = """from conans import ConanFile
from conans.util.files import load, save

class MyTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    settings = "build_type"
    build_policy = "missing"

    def build_id(self):
        self.info_build.settings.build_type = "Any"

    def build(self):
        self.output.info("Building my code!")
        save("debug/file1.txt", "Debug file1")
        save("release/file1.txt", "Release file1")

    def package(self):
        self.output.info("Packaging %s!" % self.settings.build_type)
        if self.settings.build_type == "Debug":
            self.copy("*", src="debug", keep_path=False)
        else:
            self.copy("*", src="release", keep_path=False)
"""

consumer = """[requires]
Pkg/0.1@user/channel
[imports]
., * -> .
"""


class BuildIdTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()

        client.save({"conanfile.py": conanfile})
        client.run("export user/channel")
        client.save({"conanfile.txt": consumer}, clean_first=True)
        client.run('install -s build_type=Debug')
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install -s build_type=Release')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)

        client.run("remove Pkg/0.1@user/channel -p -f")

        client.run('install -s build_type=Debug')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install -s build_type=Release')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)

        client.run("remove Pkg/0.1@user/channel -b -f")

        client.run('install -s build_type=Debug')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertNotIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install -s build_type=Release')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertNotIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)
