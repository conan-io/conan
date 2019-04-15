import os
import unittest


from conans.test.utils.tools import TestClient
from conans.util.files import load
from conans.test.utils.conanfile import TestConanFile


class CIGraphLockTest(unittest.TestCase):
    def export_lock_test(self):
        # locking a version range at export
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1"))})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        consumer = str(TestConanFile("PkgB", "0.1", requires=["PkgA/[>=0.1]@user/channel"]))
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("PkgA/0.1@user/channel#b55538d56afb03f068a054f11310ce5a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#6d56ca1040e37a13b75bc286f3e1a5ad",
                      lock_file)
        # The consumer node is None => null in json
        self.assertNotIn("PkgB", lock_file)
        client.run("export . user/testing --lock")
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("PkgB/0.1@user/testing#180919b324d7823f2683af9381d11431:Unkonwn Package ID",
                      lock_file)

    def version_ranges_lock_test(self):
        # locking a version range
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1"))})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        consumer = str(TestConanFile("PkgB", "0.1", requires=["PkgA/[>=0.1]@user/channel"]))
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)

        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("PkgA/0.1@user/channel#b55538d56afb03f068a054f11310ce5a:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#6d56ca1040e37a13b75bc286f3e1a5ad",
                      lock_file)

        # If we create a new PkgA version
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.2"))})
        client.run("create . PkgA/0.2@user/channel")

        # Normal install will use it (use install-folder to not change graph-info)
        client.save({"conanfile.py": consumer})
        client.run("install . -if=tmp")  # Output graph_info to temporary
        self.assertIn("PkgA/0.2@user/channel", client.out)
        self.assertNotIn("PkgA/0.1@user/channel", client.out)

        # Locked install will use PkgA/0.1
        # To use the stored graph_info.json, it has to be explicit in "--install-folder"
        client.run("install . -g=cmake --lock")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2@user/channel", client.out)
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("PkgA/0.1/user/channel", cmake)
        self.assertNotIn("PkgA/0.2/user/channel", cmake)

        # Info also works
        client.run("info . --lock")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)

        # Create is also possible
        # Updating the root in the graph-info file
        client.run("create . PkgB/0.1@user/channel --lock")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)

        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("PkgB/0.1@user/channel#180919b324d7823f2683af9381d11431:Unkonwn Package ID",
                      lock_file)
