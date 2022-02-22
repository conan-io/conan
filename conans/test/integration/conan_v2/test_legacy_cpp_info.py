import textwrap

from conans.test.utils.tools import TestClient


def test_legacy_names_filenames():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.components["comp"].names["cmake_find_package"] = "hello"
                self.cpp_info.components["comp"].names["cmake_find_package_multi"] = "hello"

                self.cpp_info.names["cmake_find_package"] = "absl"
                self.cpp_info.names["cmake_find_package_multi"] = "absl"
                self.cpp_info.filenames["cmake_find_package"] = "tensorflowlite"
                self.cpp_info.filenames["cmake_find_package_multi"] = "tensorflowlite"
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
