import os
import os
import shutil
import unittest
from collections import OrderedDict

from conans import DEFAULT_REVISION_V1
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import list_folder_subdirs


class SearchBinaryTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.servers["local"] = TestServer(server_capabilities=[])
        self.servers["search_able"] = TestServer(server_capabilities=[])

        client = TestClient(servers=self.servers, users={"search_able": [("lasote", "mypass")]})
        self.client = client

        # Create deps packages
        dep1_conanfile = """from conans import ConanFile
class Dep1Pkg(ConanFile):
    name = "dep"
    version = "1.0"
    settings = "os", "arch", "build_type"
    options = {"shared" : [True, False]}
    default_options = {"shared": "False"}
        """

        # Create deps packages
        foo_conanfile = """from conans import ConanFile
class FooPkg(ConanFile):
    name = "foo"
    version = "1.0"
    settings = "os", "arch", "build_type"
    options = {"shared" : [True, False]}
    default_options = {"shared": "False"}
    requires = ("dep/1.0")
                """

        self.client.save({"conanfile.py": dep1_conanfile}, clean_first=True)

        self.client.run("create . -s os=Windows -s arch=x86 -s build_type=Release")
        self.client.run("create . -s os=Windows -s arch=x86 -s build_type=Release")
        self.client.run("create . -s os=Windows -s arch=x86_64 -s build_type=Release")
        self.client.run("create . -s os=Linux -s arch=x86 -s build_type=Release")
        self.client.run("create . -s os=Linux -s arch=x86_64 -s build_type=Release")
        self.client.run("create . -s os=Macos -s arch=x86 -s build_type=Debug")
        self.client.run("create . -s os=Macos -s arch=x86_64 -s build_type=Release")

        self.client.save({"conanfile.py": foo_conanfile}, clean_first=True)

        self.client.run("create . -s os=Windows -s arch=x86 -s build_type=Release")
        self.client.run("create . -s os=Windows -s arch=x86 -s build_type=Release")
        self.client.run("create . -s os=Windows -s arch=x86_64 -s build_type=Release")
        self.client.run("create . -s os=Linux -s arch=x86 -s build_type=Release")
        self.client.run("create . -s os=Linux -s arch=x86_64 -s build_type=Release")
        self.client.run("create . -s os=Macos -s arch=x86 -s build_type=Debug")
        self.client.run("create . -s os=Macos -s arch=x86_64 -s build_type=Release")

        os.rmdir(self.servers["local"].server_store.store)
        self._copy_to_server(self.client.cache, self.servers["local"].server_store)
        os.rmdir(self.servers["search_able"].server_store.store)
        self._copy_to_server(self.client.cache, self.servers["search_able"].server_store)

    @unittest.skip("enable manually to preview output")
    def recipe_search_exact_match_test(self):
        self.client.run("search_binary"
                        " foo/1.0@ "
                        " -s os=Windows -s arch=x86 -s build_type=Release")
        print(self.client.out)

    #@unittest.skip("enable manually to preview output")
    def recipe_search_closest_match_test(self):
        self.client.run("search_binary"
                        " foo/1.0@"
                        " -s os=Windows -s arch=x86 -s build_type=Release"
                        " --closest-match"
                        " --limit 3")
        print(self.client.out)

    @staticmethod
    def _copy_to_server(cache, server_store):
        subdirs = list_folder_subdirs(basedir=cache.store, level=4)
        refs = [ConanFileReference(*folder.split("/"), revision=DEFAULT_REVISION_V1)
                for folder in subdirs]
        for ref in refs:
            origin_path = cache.package_layout(ref).export()
            dest_path = server_store.export(ref)
            shutil.copytree(origin_path, dest_path)
            server_store.update_last_revision(ref)
            packages = cache.package_layout(ref).packages()
            if not os.path.exists(packages):
                continue
            for package in os.listdir(packages):
                pref = PackageReference(ref, package, DEFAULT_REVISION_V1)
                origin_path = cache.package_layout(ref).package(pref)
                dest_path = server_store.package(pref)
                shutil.copytree(origin_path, dest_path)
                server_store.update_last_package_revision(pref)
