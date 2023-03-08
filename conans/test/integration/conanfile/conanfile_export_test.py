import unittest
import sys
import os
import textwrap
from conans.test.utils.tools import TestClient
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.mocks import RedirectedTestOutput

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

conanfile_main = GenConanfile().with_requires("pkg1/0.1","pkg2/0.1")
conanfile_main._imports.append("import myfile")
conanfile_main._imports.append("from myfile import MyClass")
conanfile_main._imports.append("from myfile import number as number")

class ExportTest(unittest.TestCase):
    def test_local_imports(self):
        c = TestClient()
        c.save({"pkg1/conanfile.py": conanfile.format(name="pkg1"),
                "pkg1/myfile.py": myfile.format(number="42"),
                "pkg2/conanfile.py": conanfile.format(name="pkg2"),
                "pkg2/myfile.py": myfile.format(number="123"),
                "app/conanfile.py": GenConanfile().with_requires("pkg1/0.1", "pkg2/0.1")})
    
        c.run("create pkg1")
        c.run("create pkg2")
        c.run("install app")
        
        # do not take any cached module
        assert "pkg1/0.1: NUMBER1: 42" in c.out
        assert "pkg1/0.1: NUMBER2: 42" in c.out
        assert "pkg1/0.1: NUMBER3: 42" in c.out
        assert "pkg2/0.1: NUMBER1: 123" in c.out
        assert "pkg2/0.1: NUMBER2: 123" in c.out
        assert "pkg2/0.1: NUMBER3: 123" in c.out
        
    def test_imports_sys_path(self):
        c = TestClient()
        
        c.save({"pkg1/conanfile.py": conanfile.format(name="pkg1"),
                "pkg1/myfile.py": myfile.format(number="42"),
                "pkg2/conanfile.py": conanfile.format(name="pkg2"),
                "pkg2/myfile.py": myfile.format(number="123"),
                "base/myfile.py": myfile.format(number="666"),
                "app/conanfile.py": conanfile_main})
    
        c.run("create pkg1")
        c.run("create pkg2")

        c.out = RedirectedTestOutput()
        base_path = os.path.join(c.current_folder, "base")
        
        try:
            sys.path.insert(0, base_path)
            __import__("myfile")
            c.run("install app")
        finally:
            sys.path.remove(base_path)
            sys.modules.pop("myfile")
            
        # take the cached module from sys.path
        assert "pkg1/0.1: NUMBER1: 666" in c.out
        assert "pkg1/0.1: NUMBER2: 666" in c.out
        assert "pkg1/0.1: NUMBER3: 666" in c.out
        assert "pkg2/0.1: NUMBER1: 666" in c.out
        assert "pkg2/0.1: NUMBER2: 666" in c.out
        assert "pkg2/0.1: NUMBER3: 666" in c.out
        
    def test_export_cached_imports_variable(self):
        c = TestClient()
        
        conanfile_app = "cached_imports = []\n" + str(conanfile_main)
        
        c.save({"pkg1/conanfile.py": conanfile.format(name="pkg1"),
                "pkg1/myfile.py": myfile.format(number="42"),
                "pkg2/conanfile.py": conanfile.format(name="pkg2"),
                "pkg2/myfile.py": myfile.format(number="123"),
                "base/myfile.py": myfile.format(number="666"),
                "app/conanfile.py": conanfile_app})
    
        c.run("create pkg1")
        c.run("create pkg2")
        
        base_path = os.path.join(c.current_folder, "base")
        try:
            sys.path.insert(0, base_path)
            c.run("install app")
        finally:
            sys.path.remove(base_path)
            
        assert "pkg1/0.1: NUMBER1: 42" in c.out
        assert "pkg1/0.1: NUMBER2: 42" in c.out
        assert "pkg1/0.1: NUMBER3: 42" in c.out
        assert "pkg2/0.1: NUMBER1: 123" in c.out
        assert "pkg2/0.1: NUMBER2: 123" in c.out
        assert "pkg2/0.1: NUMBER3: 123" in c.out
        
        
    def test_inherited_baseclass(self):
        c = TestClient()
        
        conanfile_base = textwrap.dedent("""
            from conan import ConanFile
            import os
            
            class Base(ConanFile):
                version = "0.1"
                
                def export(self):
                    self.copy('*', src=os.path.dirname(__file__), dst=self.export_folder)
                    assert os.path.isfile( os.path.join(self.export_folder, os.path.basename(__file__)) )
                
                def build(self):
                    self.output.info(f"build of {self.name}")
                    
                def package_info(self):
                    self.output.info(f"package_info of {self.name}")
                    self.output.info(f"using conanfile_base {__file__}")
        """)
        
        conanfile_pkg = textwrap.dedent("""
            import conanfile_base
            
            class Pkg(conanfile_base.Base):
                name = "{name}"
                
        """)
        
        conanfile_app = textwrap.dedent("""
            import conanfile_base
            
            class Pkg(conanfile_base.Base):
                name = "app"
                requires = "pkg1/0.1", "pkg2/0.1"
                
                def requirements(self):
                    self.output.info(f"using conanfile_base {conanfile_base.__file__}")
        """)
                
        c.save({"pkg1/conanfile.py": conanfile_pkg.format(name="pkg1"),
                "pkg2/conanfile.py": conanfile_pkg.format(name="pkg2"),
                "base/conanfile_base.py": conanfile_base,
                "app/conanfile.py": conanfile_app})
    
        
        base_path = os.path.join(c.current_folder, "base")
        try:
            sys.path.insert(0, base_path)
            c.run("export pkg1")
            c.run("export pkg2")
            c.run("install app --build=missing")
        finally:
            sys.path.remove(base_path)
            
        
        assert f"pkg1/0.1: build of pkg1" in c.out
        assert f"pkg1/0.1: package_info of pkg1" in c.out
        expected_pkg1_base = os.path.join(c.cache_folder, "data", "pkg1", "0.1", "_", "_", "export", "conanfile_base.py")
        assert f"pkg1/0.1: using conanfile_base {expected_pkg1_base}" in c.out
        
        assert f"pkg2/0.1: package_info of pkg2" in c.out
        assert f"pkg2/0.1: build of pkg2" in c.out
        expected_pkg2_base = os.path.join(c.cache_folder, "data", "pkg2", "0.1", "_", "_", "export", "conanfile_base.py")
        assert f"pkg2/0.1: using conanfile_base {expected_pkg2_base}" in c.out
        
        expected_base = os.path.join(base_path, "conanfile_base.py")
        assert f"conanfile.py (app/0.1): using conanfile_base {expected_base}" in c.out
        
        
