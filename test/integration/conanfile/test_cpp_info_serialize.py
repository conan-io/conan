import json
import textwrap

from conan.test.utils.tools import TestClient


def test_cpp_info_serialize_round_trip():
    """ test that serialize and deserialize CppInfo works
    """
    # TODO: Define standard name for file
    c = TestClient()
    conanfile = textwrap.dedent("""\
        import os
        from conan import ConanFile
        from conan.tools import CppInfo

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"

            def package(self):
                cpp_info = CppInfo(self)
                cpp_info.includedirs = ["myinc"]
                cpp_info.libs = ["mylib", "myother"]
                cpp_info.libdirs = ["mylibs"]
                p = os.path.join(self.package_folder, "cpp_info.json")
                cpp_info.save(p)

            def package_info(self):
                cpp_info = CppInfo(self).load("cpp_info.json")
                self.cpp_info = cpp_info
        """)

    c.save({"conanfile.py": conanfile})
    c.run("create . --format=json")
    graph = json.loads(c.stdout)
    cpp_info = graph["graph"]["nodes"]["1"]["cpp_info"]["root"]
    assert cpp_info["includedirs"][0].endswith("myinc")
    assert cpp_info["libdirs"][0].endswith("mylibs")
    assert cpp_info["libs"] == ["mylib", "myother"]
