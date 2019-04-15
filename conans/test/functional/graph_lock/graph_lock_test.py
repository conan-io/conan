import os
import unittest


from conans.test.utils.tools import TestClient
from conans.util.files import load
from conans.test.utils.conanfile import TestConanFile
import textwrap


class CIGraphLockTest(unittest.TestCase):
    def missing_lock_error_test(self):
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile("PkgA", "0.1"))})
        client.run("install . --lock", assert_error=True)
        self.assertIn("ERROR: Failed to load graphinfo file in install-folder", client.out)

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

    def build_require_lock_export_test(self):
        # locking a version range
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile("Tool", "0.1"))})
        client.run("create . Tool/0.1@user/channel")

        # Use a consumer with a version range
        consumer = """from conans import ConanFile
class Pkg(ConanFile):
    build_requires = "Tool/[>=0.1]@user/channel"
"""
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("Tool/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("Tool/0.1@user/channel#8f569442067ac044ca5fef316166acdb:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#5c15faa6f8c041bebd35f269cf82473f",
                      lock_file)
        # The consumer node is None => null in json
        self.assertNotIn("PkgB", lock_file)
        client.run("export . PkgB/0.1@user/channel --lock")
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("PkgB/0.1@user/channel#38c71d25e7ada04d464a57c301515fa6:Unkonwn Package ID",
                      lock_file)

    def build_require_lock_test(self):
        # locking a version range
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile("Tool", "0.1"))})
        client.run("create . Tool/0.1@user/channel")

        # Use a consumer with a version range
        consumer = """from conans import ConanFile
class Pkg(ConanFile):
    build_requires = "Tool/[>=0.1]@user/channel"
"""
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("Tool/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("Tool/0.1@user/channel#8f569442067ac044ca5fef316166acdb:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9#5c15faa6f8c041bebd35f269cf82473f",
                      lock_file)

        # If we create a new PkgA version
        client.save({"conanfile.py": str(TestConanFile("Tool", "0.2"))})
        client.run("create . Tool/0.2@user/channel")

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        client.run("install . -if=tmp")
        self.assertIn("Tool/0.2@user/channel", client.out)
        self.assertNotIn("Tool/0.1@user/channel", client.out)

        # Locked install will use PkgA/0.1
        client.run("install . -g=cmake --lock")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("Tool/0.1/user/channel", cmake)
        self.assertNotIn("Tool/0.2/user/channel", cmake)

        # Info also works
        client.run("info . --lock")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2/user/channel", client.out)

        # create also works
        client.run("create . PkgB/0.1@user/channel --lock")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2/user/channel", client.out)
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        self.assertIn("PkgB/0.1@user/channel#38c71d25e7ada04d464a57c301515fa6:Unkonwn Package ID",
                      lock_file)

    def python_requires_lock_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            var = 42
            class Pkg(ConanFile):
                pass
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . Tool/0.1@user/channel")

        # Use a consumer with a version range
        consumer = textwrap.dedent("""
            from conans import ConanFile, python_requires
            dep = python_requires("Tool/[>=0.1]@user/channel")

            class Pkg(ConanFile):
                def build(self):
                    self.output.info("VAR=%s" % dep.var)
            """)
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("Tool/0.1@user/channel", client.out)
        client.run("build .")
        self.assertIn("conanfile.py: VAR=42", client.out)
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        print lock_file
        self.assertIn("Tool/0.1@user/channel", lock_file)

        # If we create a new Tool version
        client.save({"conanfile.py": conanfile.replace("42", "24")})
        client.run("export . Tool/0.2@user/channel")

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        # Make sure to use temporary if to not change graph_info.json
        client.run("install . -if=tmp")
        self.assertIn("Tool/0.2@user/channel", client.out)
        client.run("build .")
        self.assertIn("conanfile.py: VAR=24", client.out)

        # Locked create will use Tool/0.1
        # Updating the root in the graph-info file
        client.run("install . Pkg/0.1@user/channel --graph-info=.")
        print client.out
        lock_file = load(os.path.join(client.current_folder, "graph_info.json"))
        print lock_file
        self.assertIn("Tool/0.1@user/channel", lock_file)
        client.run("create . Pkg/0.1@user/channel --graph-info=.")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
