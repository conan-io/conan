import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load, save
from time import sleep
import time
from conans.paths import CONAN_MANIFEST


class InstallUpdateTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

    def update_binaries_test(self):
        conanfile = """from conans import ConanFile
from conans.tools import save
import os, random
class Pkg(ConanFile):
    def package(self):
        save(os.path.join(self.package_folder, "file.txt"), str(random.random()))
    def deploy(self):
        self.copy("file.txt")
"""
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . Pkg/0.1@lasote/testing")
        self.client.run("upload Pkg/0.1@lasote/testing --all -r=myremote")

        client2 = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})
        client2.run("install Pkg/0.1@lasote/testing")
        value = load(os.path.join(client2.current_folder, "file.txt"))

        time.sleep(1)  # Make sure the new timestamp is later
        self.client.run("create . Pkg/0.1@lasote/testing")
        self.client.run("upload Pkg/0.1@lasote/testing --all")

        client2.run("install Pkg/0.1@lasote/testing")
        new_value = load(os.path.join(client2.current_folder, "file.txt"))
        self.assertEqual(value, new_value)

        client2.run("install Pkg/0.1@lasote/testing --update")
        self.assertIn("Current package is older than remote upstream one", client2.out)
        new_value = load(os.path.join(client2.current_folder, "file.txt"))
        self.assertNotEqual(value, new_value)

        # Now check newer local modifications are not overwritten
        time.sleep(1)  # Make sure the new timestamp is later
        self.client.run("create . Pkg/0.1@lasote/testing")
        self.client.run("upload Pkg/0.1@lasote/testing --all")

        client2.save({"conanfile.py": conanfile})
        client2.run("create . Pkg/0.1@lasote/testing")
        client2.run("install Pkg/0.1@lasote/testing")
        value2 = load(os.path.join(client2.current_folder, "file.txt"))
        client2.run("install Pkg/0.1@lasote/testing --update")
        self.assertIn("Current package is newer than remote upstream one", client2.out)
        new_value = load(os.path.join(client2.current_folder, "file.txt"))
        self.assertEqual(value2, new_value)

    def update_binaries_failed_test(self):
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing --update")
        self.assertIn("Pkg/0.1@lasote/testing: WARN: Can't update, no remote defined",
                      client.out)

    def update_binaries_no_package_error_test(self):
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        client.run("upload Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing --update")
        self.assertIn("Pkg/0.1@lasote/testing: WARN: Can't update, no package in remote",
                      client.out)

    def update_not_date_test(self):
        # Regression for https://github.com/conan-io/conan/issues/949
        files0 = cpp_hello_conan_files("Hello0", "1.0", build=False)
        files0["conanfile.py"] = files0["conanfile.py"].replace("settings = ", "# settings = ")
        self.client.save(files0)
        self.client.run("export . lasote/stable")
        files1 = cpp_hello_conan_files("Hello1", "1.0", build=False,
                                       deps=["Hello0/1.0@lasote/stable"])
        self.client.save(files1, clean_first=True)
        self.client.run("install . --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
        package_ref = PackageReference(ref, "55a3af76272ead64e6f543c12ecece30f94d3eda")
        export_folder = self.client.client_cache.export(ref)
        recipe_manifest = os.path.join(export_folder, CONAN_MANIFEST)
        package_folder = self.client.client_cache.package(package_ref)
        package_manifest = os.path.join(package_folder, CONAN_MANIFEST)

        def timestamps():
            recipe_timestamp = load(recipe_manifest).splitlines()[0]
            package_timestamp = load(package_manifest).splitlines()[0]
            return recipe_timestamp, package_timestamp

        initial_timestamps = timestamps()

        time.sleep(1)

        # Change and rebuild package
        files0["helloHello0.h"] = files0["helloHello0.h"] + " // useless comment"
        self.client.save(files0, clean_first=True)
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        rebuild_timestamps = timestamps()
        self.assertNotEqual(rebuild_timestamps, initial_timestamps)

        # back to the consumer, try to update
        self.client.save(files1, clean_first=True)
        self.client.run("install . --update")
        self.assertIn("Hello0/1.0@lasote/stable from 'myremote' - Newer",
                      self.client.out)
        failed_update_timestamps = timestamps()
        self.assertEqual(rebuild_timestamps, failed_update_timestamps)

        # hack manifests, put old time
        for manifest_file in (recipe_manifest, package_manifest):
            manifest = load(manifest_file)
            lines = manifest.splitlines()
            lines[0] = "123"
            save(manifest_file, "\n".join(lines))

        self.client.run("install . --update")
        update_timestamps = timestamps()
        self.assertEqual(update_timestamps, initial_timestamps)

    def reuse_test(self):
        files = cpp_hello_conan_files("Hello0", "1.0", build=False)

        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client2.run("install Hello0/1.0@lasote/stable")

        files["helloHello0.h"] = "//EMPTY!"
        self.client.save(files, clean_first=True)
        sleep(1)
        self.client.run("export . lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        client2.run("install Hello0/1.0@lasote/stable --update")
        ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
        package_ids = client2.paths.conan_packages(ref)
        package_path = client2.paths.package(PackageReference(ref, package_ids[0]))
        header = load(os.path.join(package_path, "include/helloHello0.h"))
        self.assertEqual(header, "//EMPTY!")

    def remove_old_sources_test(self):
        # https://github.com/conan-io/conan/issues/1841
        test_server = TestServer()

        def upload(header_content):
            client = TestClient(servers={"default": test_server},
                                users={"default": [("lasote", "mypass")]})
            base = '''from conans import ConanFile
class ConanLib(ConanFile):
    exports_sources = "*"
    def package(self):
        self.copy("*")
'''
            client.save({"conanfile.py": base,
                         "header.h": header_content})
            client.run("create . Pkg/0.1@lasote/channel")
            client.run("upload * --confirm --all")
            return client

        client = upload("mycontent1")
        time.sleep(1)
        upload("mycontent2")

        client.run("install Pkg/0.1@lasote/channel -u")
        self.assertIn("Pkg/0.1@lasote/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update", client.out)
        self.assertIn("Pkg/0.1@lasote/channel: Retrieving package 5ab84d6acfe1f2", client.out)
        conan_ref = ConanFileReference.loads("Pkg/0.1@lasote/channel")
        pkg_ref = PackageReference(conan_ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        header = os.path.join(client.client_cache.package(pkg_ref), "header.h")
        self.assertEqual(load(header), "mycontent2")
