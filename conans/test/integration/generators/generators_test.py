import textwrap

from conans.test.utils.tools import TestClient


class TestGenerators:

    def test_error(self):
        client = TestClient()
        client.save({"conanfile.txt": "[generators]\nunknown"})
        client.run("install . --build=*", assert_error=True)
        assert "ERROR: Invalid generator 'unknown'. Available types:" in client.out

    def test_generate_package_folder_deprecation(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                def generate(self):
                    self.package_folder
                """)
        c.save({"conanfile.py": conanfile})
        c.run("install .")
        assert "ERROR: 'self.package_folder' can't be used in 'generate()'" in c.out
