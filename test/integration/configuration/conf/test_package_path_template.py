import os
import textwrap
import unittest

from conan.test.utils.tools import TestClient
from conan.test.utils.test_files import temp_folder
from conan.api.output import ConanOutput
from conan.internal.util.files import save, load


class PackagePathTemplateTest(unittest.TestCase):

    def test_package_path_template(self):
        """ Test that the package path template works correctly """
        # Create a test client with our custom template
        client = TestClient()
        save(os.path.join(client.cache_folder, "global.conf"),
             "core.cache:package_path_template = {pkgname}\n")

        # Create a simple package
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            
            class TestConan(ConanFile):
                name = "hello"
                version = "1.0"
                
                def package(self):
                    self.output.info("Packaging...")
                    save(self, os.path.join(self.package_folder, "hello.txt"), "Hello World!")
            """)
        
        client.save({"conanfile.py": conanfile})
        client.run("create .")
        
        # Verify the package was created with the custom template
        package_ref = client.created_package_reference("hello/1.0")
        package_path = client.packlayout(package_ref).package()
        
        # Check that the path contains /hello/ as per our template
        self.assertIn("/hello/", package_path)
        
        # Verify the package content is accessible
        hello_path = os.path.join(package_path, "hello.txt")
        self.assertTrue(os.path.exists(hello_path))
        self.assertEqual(load(hello_path), "Hello World!")
        
    def test_template_with_version(self):
        """ Test that the package path template works with version """
        # Create a test client with custom template including version
        client = TestClient()
        save(os.path.join(client.cache_folder, "global.conf"),
             "core.cache:package_path_template = {pkgname}-{version}\n")

        # Create a simple package
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            
            class TestConan(ConanFile):
                name = "hello"
                version = "2.0"
                
                def package(self):
                    self.output.info("Packaging...")
                    save(self, os.path.join(self.package_folder, "hello.txt"), "Hello World!")
            """)
        
        client.save({"conanfile.py": conanfile})
        client.run("create .")
        
        # Verify the package was created with the custom template
        package_ref = client.created_package_reference("hello/2.0")
        package_path = client.packlayout(package_ref).package()
        
        # Check that the path contains /hello-2.0/ as per our template
        self.assertIn("hello-2.0", package_path)
        
        # Verify the package content is accessible
        hello_path = os.path.join(package_path, "hello.txt")
        self.assertTrue(os.path.exists(hello_path))
        self.assertEqual(load(hello_path), "Hello World!")
