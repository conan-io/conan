import os
import unittest

from nose_parameterized.parameterized import parameterized

from conans.model.ref import PackageReference, ConanFileReference
from conans.test.utils.tools import TestClient
from conans.util.files import load

conanfile = """from conans import ConanFile
from conans.util.files import save

class MyTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    settings = "os", "build_type"
    build_policy = "missing"

    def build_id(self):
        if self.settings.os == "Windows":
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

consumer_py = """from conans import ConanFile


class MyTest(ConanFile):
    name = "MyTest"
    version = "0.1"
    settings = "os", "build_type"
    requires = "Pkg/0.1@user/channel"

    def build_id(self):
        self.info_build.settings.build_type = "Any"
        self.info_build.requires.clear()

    def imports(self):
        self.copy("*")
"""


class BuildIdTest(unittest.TestCase):
    def _check_conaninfo(self, client):
        # Check that conaninfo is correct
        ref_debug = PackageReference.loads("Pkg/0.1@user/channel:"
                                           "f3989dcba0ab50dc5ed9b40ede202bdd7b421f09")
        conaninfo = load(os.path.join(client.client_cache.package(ref_debug), "conaninfo.txt"))
        self.assertIn("os=Windows", conaninfo)
        self.assertIn("build_type=Debug", conaninfo)
        self.assertNotIn("Release", conaninfo)

        ref_release = PackageReference.loads("Pkg/0.1@user/channel:"
                                             "ab2e9f86b4109980930cdc685f4a320b359e7bb4")
        conaninfo = load(os.path.join(client.client_cache.package(ref_release), "conaninfo.txt"))
        self.assertIn("os=Windows", conaninfo)
        self.assertIn("build_type=Release", conaninfo)
        self.assertNotIn("Debug", conaninfo)

        ref_debug = PackageReference.loads("Pkg/0.1@user/channel:"
                                           "322de4b4a41f905f6b18f454ab5f498690b39c2a")
        conaninfo = load(os.path.join(client.client_cache.package(ref_debug), "conaninfo.txt"))
        self.assertIn("os=Linux", conaninfo)
        self.assertIn("build_type=Debug", conaninfo)
        self.assertNotIn("Release", conaninfo)

        ref_release = PackageReference.loads("Pkg/0.1@user/channel:"
                                             "24c3aa2d6c5929d53bd86b31e020c55d96b265c7")
        conaninfo = load(os.path.join(client.client_cache.package(ref_release), "conaninfo.txt"))
        self.assertIn("os=Linux", conaninfo)
        self.assertIn("build_type=Release", conaninfo)
        self.assertNotIn("Debug", conaninfo)

    def create_test(self):
        """ Ensure that build_id() works when multiple create calls are made
        """
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . user/channel -s os=Windows -s build_type=Release")
        self.assertIn("Pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        client.run("create . user/channel -s os=Windows -s build_type=Debug")
        self.assertNotIn("Pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Packaging Debug!", client.user_io.out)

        client.run("create . user/channel -s os=Linux -s build_type=Release")
        self.assertIn("Pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        client.run("create . user/channel -s os=Linux -s build_type=Debug")
        self.assertIn("Pkg/0.1@user/channel: Calling build()", client.out)
        self.assertIn("Packaging Debug!", client.user_io.out)
        self._check_conaninfo(client)

    @parameterized.expand([(True, ), (False,)])
    def basic_test(self, python_consumer):
        client = TestClient()

        client.save({"conanfile.py": conanfile})
        client.run("export . user/channel")
        if python_consumer:
            client.save({"conanfile.py": consumer_py}, clean_first=True)
        else:
            client.save({"conanfile.txt": consumer}, clean_first=True)
        client.run('install . -s os=Windows -s build_type=Debug')
        self.assertIn("Building package from source as defined by build_policy='missing'",
                      client.user_io.out)
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Windows -s build_type=Release')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)
        # Now Linux
        client.run('install . -s os=Linux -s build_type=Debug')
        self.assertIn("Building package from source as defined by build_policy='missing'",
                      client.user_io.out)
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Linux -s build_type=Release')
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)
        self._check_conaninfo(client)

        # Check that repackaging works, not necessary to re-build
        client.run("remove Pkg/0.1@user/channel -p -f")
        client.run('install . -s os=Windows -s build_type=Debug')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Windows -s build_type=Release')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)
        # Now Linux
        client.run('install . -s os=Linux -s build_type=Debug')
        self.assertIn("Building package from source as defined by build_policy='missing'",
                      client.user_io.out)
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Linux -s build_type=Release')
        self.assertIn("Building my code!", client.user_io.out)
        self.assertIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)
        self._check_conaninfo(client)

        # But if the build folder is removed, the packages are there, do nothing
        client.run("remove Pkg/0.1@user/channel -b -f")
        client.run('install . -s os=Windows -s build_type=Debug')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertNotIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Windows -s build_type=Release')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertNotIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)
        # Now Linux
        client.run('install . -s os=Linux -s build_type=Debug')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertNotIn("Packaging Debug!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Debug file1", content)
        client.run('install . -s os=Linux -s build_type=Release')
        self.assertNotIn("Building my code!", client.user_io.out)
        self.assertNotIn("Packaging Release!", client.user_io.out)
        content = load(os.path.join(client.current_folder, "file1.txt"))
        self.assertEqual("Release file1", content)
        self._check_conaninfo(client)

    def remove_specific_builds_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run('create . user/channel -s os=Windows -s build_type=Debug')
        client.run('create . user/channel -s os=Windows -s build_type=Release')
        ref = ConanFileReference.loads("Pkg/0.1@user/channel")

        def _check_builds():
            builds = client.client_cache.conan_builds(ref)
            self.assertEqual(1, len(builds))
            packages = client.client_cache.conan_packages(ref)
            self.assertEqual(2, len(packages))
            self.assertNotIn(builds[0], packages)
            return builds[0], packages

        build, packages = _check_builds()
        client.run("remove Pkg/0.1@user/channel -b %s -f" % packages[0])
        _check_builds()
        client.run("remove Pkg/0.1@user/channel -b %s -f" % build)
        builds = client.client_cache.conan_builds(ref)
        self.assertEqual(0, len(builds))
        packages = client.client_cache.conan_packages(ref)
        self.assertEqual(2, len(packages))

    @parameterized.expand([(True, ), (False,)])
    def info_test(self, python_consumer):
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . user/channel")
        if python_consumer:
            client.save({"conanfile.py": consumer_py}, clean_first=True)
        else:
            client.save({"conanfile.txt": consumer}, clean_first=True)
        client.run('install . -s os=Windows -s build_type=Debug')
        client.run('install . -s os=Windows -s build_type=Release')
        client.run("info .")  # Uses release

        def _check():
            build_ids = str(client.out).count("BuildID: 427f426a482a2b22a1744e9e949aa7f2544f5b7c")
            build_nones = str(client.out).count("BuildID: None")
            if python_consumer:
                self.assertEqual(2, build_ids)
                self.assertEqual(0, build_nones)
            else:
                self.assertEqual(1, build_ids)
                self.assertEqual(1, build_nones)

        _check()
        self.assertIn("ID: ab2e9f86b4109980930cdc685f4a320b359e7bb4", client.out)
        self.assertNotIn("ID: f3989dcba0ab50dc5ed9b40ede202bdd7b421f09", client.out)

        client.run("info . -s os=Windows -s build_type=Debug")
        _check()
        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.out)
        self.assertIn("ID: f3989dcba0ab50dc5ed9b40ede202bdd7b421f09", client.out)

        if python_consumer:
            client.run("export . user/channel")
            client.run("info MyTest/0.1@user/channel -s os=Windows -s build_type=Debug")
            _check()
            self.assertNotIn("ID: ab2e9f86b4109980930cdc685f4a320b359e7bb4", client.out)
            self.assertIn("ID: f3989dcba0ab50dc5ed9b40ede202bdd7b421f09", client.out)
            client.run("info MyTest/0.1@user/channel -s os=Windows -s build_type=Release")
            _check()
            self.assertIn("ID: ab2e9f86b4109980930cdc685f4a320b359e7bb4", client.out)
            self.assertNotIn("ID: f3989dcba0ab50dc5ed9b40ede202bdd7b421f09", client.out)
