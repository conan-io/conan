import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import load


class NewTest(unittest.TestCase):

    def new_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_dash_test(self):
        """ packages with dash
        """
        client = TestClient()
        client.run('new My-Package/1.3@myuser/testing -t')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "My-Package"', content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("My-Package/1.3@myuser/testing", client.user_io.out)

    def new_header_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t -i')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertTrue(os.path.exists(os.path.join(root, "test_package/example.cpp")))
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_sources_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -t -s')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertIn('exports_sources', content)
        self.assertNotIn('source()', content)
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_purec_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing -c -t')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        content = load(os.path.join(root, "conanfile.py"))
        self.assertIn('name = "MyPackage"', content)
        self.assertIn('version = "1.3"', content)
        self.assertIn('del self.settings.compiler.libcxx', content)
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("MyPackage/1.3@myuser/testing", client.user_io.out)

    def new_without_test(self):
        client = TestClient()
        client.run('new MyPackage/1.3@myuser/testing')
        root = client.current_folder
        self.assertTrue(os.path.exists(os.path.join(root, "conanfile.py")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/conanfile.py")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/CMakeLists.txt")))
        self.assertFalse(os.path.exists(os.path.join(root, "test_package/example.cpp")))
