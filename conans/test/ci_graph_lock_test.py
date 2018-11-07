import json
import os
import unittest

from conans.model.ref import PackageReference
from conans.test.utils.tools import TestClient
from conans.util.files import load


class CIGraphLockTest(unittest.TestCase):
    def python_requires_lock_test(self):
        # locking a version range
        client = TestClient()
        conanfile = """from conans import ConanFile
var = 42
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Tool/0.1@user/channel")

        # Use a consumer with a version range
        consumer = """from conans import ConanFile, python_requires
dep = python_requires("Tool/[>=0.1]@user/channel")

class Pkg(ConanFile):
    def build(self):
        self.output.info("VAR=%s" % dep.var)
"""
        client.save({"conanfile.py": consumer})
        client.run("create . Pkg/0.1@user/channel --output-lock=default.lock")
        out = "".join(str(client.out).splitlines())
        self.assertIn("Python requires    Tool/0.1@user/channel", out)
        self.assertIn("Pkg/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build",
                      out)
        self.assertIn("Pkg/0.1@user/channel: VAR=42", out)
        lock_file = load(os.path.join(client.current_folder, "default.lock"))
        self.assertIn("Pkg/0.1@user/channel", lock_file)
        self.assertIn("Tool/0.1@user/channel", lock_file)

        # If we create a new Tool version
        client.save({"conanfile.py": conanfile.replace("42", "24")})
        client.run("create . Tool/0.2@user/channel")

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        client.run("create . Pkg/0.1@user/channel")
        print client.out
        out = "".join(str(client.out).splitlines())
        self.assertIn("Python requires    Tool/0.2@user/channel", out)
        self.assertIn("Pkg/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Build",
                      out)
        self.assertIn("Pkg/0.1@user/channel: VAR=24", out)

        # Locked install will use Tool/0.1
        client.run("create . Pkg/0.1@user/channel --input-lock=default.lock")
        print client.out
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)

        # Info also works
        client.run("info . --input-lock=default.lock")
        print client.out
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)

    def version_ranges_lock_test(self):
        # locking a version range
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . PkgA/0.1@user/channel")

        # Use a consumer with a version range
        consumer = """from conans import ConanFile
class Pkg(ConanFile):
    requires = "PkgA/[>=0.1]@user/channel"
"""
        client.save({"conanfile.py": consumer})
        client.run("install . --output-lock=default.lock")
        self.assertIn("PkgA/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        lock_file = load(os.path.join(client.current_folder, "default.lock"))
        self.assertIn("PkgA/0.1@user/channel", lock_file)

        # If we create a new PkgA version
        client.save({"conanfile.py": conanfile})
        client.run("create . PkgA/0.2@user/channel")

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("PkgA/0.2@user/channel", client.out)
        self.assertNotIn("PkgA/0.1@user/channel", client.out)

        # Locked install will use PkgA/0.1
        client.run("install . --input-lock=default.lock -g=cmake")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2@user/channel", client.out)
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("PkgA/0.1/user/channel", cmake)
        self.assertNotIn("PkgA/0.2/user/channel", cmake)

        # Info also works
        client.run("info . --input-lock=default.lock")
        self.assertIn("PkgA/0.1@user/channel", client.out)
        self.assertNotIn("PkgA/0.2/user/channel", client.out)

    def build_require_lock_test(self):
        # locking a version range
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Tool/0.1@user/channel")

        # Use a consumer with a version range
        consumer = """from conans import ConanFile
class Pkg(ConanFile):
    build_requires = "Tool/[>=0.1]@user/channel"
"""
        client.save({"conanfile.py": consumer})
        client.run("install . --output-lock=default.lock")
        self.assertIn("Tool/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        lock_file = load(os.path.join(client.current_folder, "default.lock"))
        self.assertIn("Tool/0.1@user/channel", lock_file)

        # If we create a new PkgA version
        client.save({"conanfile.py": conanfile})
        client.run("create . Tool/0.2@user/channel")

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("Tool/0.2@user/channel", client.out)
        self.assertNotIn("Tool/0.1@user/channel", client.out)

        # Locked install will use PkgA/0.1
        client.run("install . --input-lock=default.lock -g=cmake")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("Tool/0.1/user/channel", cmake)
        self.assertNotIn("Tool/0.2/user/channel", cmake)

        # Info also works
        client.run("info . --input-lock=default.lock")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2/user/channel", client.out)

    def build_require_multi_lock_test(self):
        # locking a version range
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Tool/0.1@user/channel")
        client.run("create . Tool2/0.1@user/channel")

        # Use a consumer with a version range
        consumer = """from conans import ConanFile
class Pkg(ConanFile):
    build_requires = "Tool/[>=0.1]@user/channel", "Tool2/[>=0.1]@user/channel"
"""
        client.save({"conanfile.py": consumer})
        client.run("install . --output-lock=default.lock")
        self.assertIn("Tool/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        self.assertIn("Tool2/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)
        lock_file = load(os.path.join(client.current_folder, "default.lock"))
        self.assertIn("Tool/0.1@user/channel", lock_file)
        self.assertIn("Tool2/0.1@user/channel", lock_file)

        # If we create a new PkgA version
        client.save({"conanfile.py": conanfile})
        client.run("create . Tool/0.2@user/channel")
        client.run("create . Tool2/0.2@user/channel")

        # Normal install will use it
        client.save({"conanfile.py": consumer})
        client.run("install .")
        self.assertIn("Tool/0.2@user/channel", client.out)
        self.assertNotIn("Tool/0.1@user/channel", client.out)
        self.assertIn("Tool2/0.2@user/channel", client.out)
        self.assertNotIn("Tool2/0.1@user/channel", client.out)

        # Locked install will use PkgA/0.1
        client.run("install . --input-lock=default.lock -g=cmake")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2@user/channel", client.out)
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("Tool/0.1/user/channel", cmake)
        self.assertNotIn("Tool/0.2/user/channel", cmake)
        self.assertIn("Tool2/0.1/user/channel", cmake)
        self.assertNotIn("Tool2/0.2/user/channel", cmake)

        # Info also works
        client.run("info . --input-lock=default.lock")
        self.assertIn("Tool/0.1@user/channel", client.out)
        self.assertNotIn("Tool/0.2/user/channel", client.out)
        self.assertIn("Tool2/0.1@user/channel", client.out)
        self.assertNotIn("Tool2/0.2/user/channel", client.out)

    def option_lock_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"custom_option": [1, 2, 3, 4, 5]}
    default_options = "custom_option=1"
    %s
"""
        client.save({"conanfile.py": conanfile % ""})
        client.run("create . PkgA/0.1@user/channel -o PkgA:custom_option=2")
        self.assertIn("PkgA/0.1@user/channel:ff96d88607d8cfb182c50ad39b2c73b5ef569728 - Build",
                      client.out)

        # Dependent PkgB -> PkgA
        client.save({"conanfile.py": conanfile % "requires = 'PkgA/0.1@user/channel'"})
        client.run("info . -o PkgA:custom_option=2 --output-lock=conan_graph.lock")
        self.assertIn("ID: ff96d88607d8cfb182c50ad39b2c73b5ef569728",
                      client.out)

        # client.run("graph root conan_graph.lock PkgB/0.1@user/testing")
        client.run("create . PkgB/0.1@user/testing --input-lock=conan_graph.lock")
        self.assertIn("PkgA/0.1@user/channel:ff96d88607d8cfb182c50ad39b2c73b5ef569728 - Cache",
                      client.out)
        self.assertIn("PkgB/0.1@user/testing: Package 'be80f811c336669e69eb58adc8215ce32ac1ba6f' "
                      "created", client.out)

    def graph_lock_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"custom_option": [1, 2, 3, 4, 5]}
    default_options = "custom_option=1"
    %s
"""
        client.save({"conanfile.py": conanfile % ""})
        client.run("export . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile % "requires = 'PkgA/0.1@user/channel'"})
        client.run("export . PkgB/0.1@user/channel")
        client.save({"conanfile.py": conanfile % "requires = 'PkgB/0.1@user/channel'"})
        client.run("export . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile % "requires = 'PkgC/0.1@user/channel'"})

        client.run("info . -o PkgA:custom_option=2 "
                   "-o PkgB:custom_option=3 -o PkgC:custom_option=4 --output-loc=options.lock")

        out = "".join(str(client.out).splitlines())
        self.assertIn("PkgA/0.1@user/channel    ID: ff96d88607d8cfb182c50ad39b2c73b5ef569728",
                      out)
        self.assertIn("PkgB/0.1@user/channel    ID: af3515bc3fcd0aa30f4f719830d1bdb6eb46379a",
                      out)
        self.assertIn("PkgC/0.1@user/channel    ID: a1f49d2fd08c58cbc75961f109afb1a585c20bbe",
                      out)
        lock_file = load(os.path.join(client.current_folder, "options.lock"))
        self.assertIn("PkgC:custom_option=4", lock_file)
        self.assertIn("PkgB:custom_option=3", lock_file)
        self.assertIn("PkgA:custom_option=2", lock_file)

        client.run("info . --build-order=ALL --input-lock=options.lock")

        build_order_file = os.path.join(client.current_folder, "options_build_order.json")
        content = load(build_order_file)
        build_order = json.loads(content)
        # Checking A
        self.assertEqual(3, len(build_order))
        level = build_order[0]
        self.assertEqual(1, len(level))
        self.assertEqual("PkgA/0.1@user/channel:ff96d88607d8cfb182c50ad39b2c73b5ef569728",
                         level[0])
        r = PackageReference.loads(level[0])
        conan_ref = r.conan
        client.run("install %s --input-lock=options.lock --build=%s"
                   % (conan_ref, conan_ref.name))
        self.assertIn("PkgA/0.1@user/channel:ff96d88607d8cfb182c50ad39b2c73b5ef569728", client.out)

        # Checking B
        level = build_order[1]
        self.assertEqual(1, len(level))
        self.assertEqual("PkgB/0.1@user/channel:af3515bc3fcd0aa30f4f719830d1bdb6eb46379a",
                         level[0])
        r = PackageReference.loads(level[0])
        conan_ref = r.conan
        client.run("install %s --input-lock=options.lock --build=%s"
                   % (conan_ref, conan_ref.name))
        self.assertIn("PkgA/0.1@user/channel:ff96d88607d8cfb182c50ad39b2c73b5ef569728", client.out)
        self.assertIn("PkgB/0.1@user/channel:af3515bc3fcd0aa30f4f719830d1bdb6eb46379a", client.out)

        # Checking C
        level = build_order[2]
        self.assertEqual(1, len(level))
        self.assertEqual("PkgC/0.1@user/channel:a1f49d2fd08c58cbc75961f109afb1a585c20bbe",
                         level[0])
        r = PackageReference.loads(level[0])
        conan_ref = r.conan
        client.run("install %s --input-lock=options.lock --build=%s"
                   % (conan_ref, conan_ref.name))
        self.assertIn("PkgA/0.1@user/channel:ff96d88607d8cfb182c50ad39b2c73b5ef569728", client.out)
        self.assertIn("PkgB/0.1@user/channel:af3515bc3fcd0aa30f4f719830d1bdb6eb46379a", client.out)
        self.assertIn("PkgC/0.1@user/channel:a1f49d2fd08c58cbc75961f109afb1a585c20bbe", client.out)
