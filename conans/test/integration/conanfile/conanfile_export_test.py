import unittest
import sys
import os
import textwrap
from conans.test.utils.tools import TestClient
from conans.test.assets.genconanfile import GenConanfile

class ExportTest(unittest.TestCase):
    def mytest_repeated_imports_same_name(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            import myfile
            from myfile import MyClass
            from myfile import number as number
            class Pkg(ConanFile):
                name = "{name}"
                version = "0.1"
                exports = "myfile.py"
    
                def package_info(self):
                    self.output.info(f"NUMBER1: {{myfile.number}}")
                    self.output.info(f"NUMBER2: {{MyClass.number}}")
                    self.output.info(f"NUMBER3: {{number}}")
                """)
        myfile = textwrap.dedent("""\
            number = {number}
    
            class MyClass:
                number = {number}
            """)
        c.save({"pkg1/conanfile.py": conanfile.format(name="pkg1"),
                "pkg1/myfile.py": myfile.format(number="42"),
                "pkg2/conanfile.py": conanfile.format(name="pkg2"),
                "pkg2/myfile.py": myfile.format(number="123"),
                "app/conanfile.py": GenConanfile().with_requires("pkg1/0.1", "pkg2/0.1")})
    
        c.run("create pkg1")
        c.run("create pkg2")
        c.run("install app")
        assert "pkg1/0.1: NUMBER1: 42" in c.out
        assert "pkg1/0.1: NUMBER2: 42" in c.out
        assert "pkg1/0.1: NUMBER3: 42" in c.out
        assert "pkg2/0.1: NUMBER1: 123" in c.out
        assert "pkg2/0.1: NUMBER2: 123" in c.out
        assert "pkg2/0.1: NUMBER3: 123" in c.out
        
    def test_export_from_sibling_directory(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            import myfile
            from myfile import MyClass
            from myfile import number as number
            class Pkg(ConanFile):
                name = "{name}"
                version = "0.1"
                exports = "myfile.py"
    
                def package_info(self):
                    self.output.info(f"NUMBER1: {{myfile.number}}")
                    self.output.info(f"NUMBER2: {{MyClass.number}}")
                    self.output.info(f"NUMBER3: {{number}}")
                """)
        myfile = textwrap.dedent("""\
            number = {number}
    
            class MyClass:
                number = {number}
            """)
        
        conanfile_main = GenConanfile().with_requires("pkg1/0.1")
        conanfile_main._imports.append("import myfile")
        conanfile_main._imports.append("from myfile import MyClass")
        conanfile_main._imports.append("from myfile import number as number")
        c.save({"pkg1/conanfile.py": conanfile.format(name="pkg1"),
                "pkg1/myfile.py": myfile.format(number="42"),
                "base/myfile.py": myfile.format(number="123"),
                "app/conanfile.py": conanfile_main})
    
        c.run("create pkg1")
        base_path = os.path.join(c.current_folder, "base")
        try:
            sys.path.insert(0, base_path)
            c.run("install app")
        finally:
            sys.path.remove(base_path)
            
        assert not "pkg1/0.1: NUMBER1: 123" in c.out
        assert not "pkg1/0.1: NUMBER2: 123" in c.out
        assert not "pkg1/0.1: NUMBER3: 123" in c.out
        assert "pkg1/0.1: NUMBER1: 42" in c.out
        assert "pkg1/0.1: NUMBER2: 42" in c.out
        assert "pkg1/0.1: NUMBER3: 42" in c.out
