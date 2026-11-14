import textwrap

import pytest

from conan.internal.model.conan_file import ConanFile
from conan.internal.model.cpp_info import CppInfo
from conan.test.utils.tools import TestClient


class TestConanFile:
    def test_conanfile_naming(self):
        for member in vars(ConanFile):
            if member.startswith('_') and not member.startswith("__"):
                assert member.startswith('_conan')

        conanfile = ConanFile(None)

        for member in vars(conanfile):
            if member.startswith('_') and not member.startswith("__"):
                assert member.startswith('_conan')

    def test_layouts_are_created_on_first_access(self):
        conanfile, other = ConanFile(None), ConanFile(None)
        assert not vars(conanfile.layouts)  # nothing is allocated until it is used
        for name in ("source", "build", "package"):
            layout = getattr(conanfile.layouts, name)
            assert layout is getattr(conanfile.layouts, name)
            assert not layout.buildenv_info and not layout.runenv_info and not layout.conf_info
            assert layout is not getattr(other.layouts, name)

        conanfile.layouts.build.buildenv_info.define("MYVAR", "myvalue")
        conanfile.layouts.package.conf_info.define("user.my:conf", "myvalue")
        assert conanfile.layouts.build.buildenv_info
        assert conanfile.layouts.package.conf_info
        assert not other.layouts.build.buildenv_info
        assert not other.layouts.package.conf_info
        assert not conanfile.layouts.source.buildenv_info

    def test_cpp_infos_are_created_on_first_access(self):
        conanfile, other = ConanFile(None), ConanFile(None)
        assert not vars(conanfile.cpp)
        for index, name in enumerate(("source", "build", "package"), start=1):
            info = getattr(conanfile.cpp, name)
            assert len(vars(conanfile.cpp)) == index
            assert info is getattr(conanfile.cpp, name)
            assert info.serialize() == CppInfo(set_defaults=name == "package").serialize()
            info.libs.append(name)
            info.components["component"].defines.append(name)
            assert getattr(conanfile.cpp, name).libs == [name]
            assert getattr(conanfile.cpp, name).components["component"].defines == [name]
            assert not getattr(other.cpp, name).libs
            assert not getattr(other.cpp, name).components

    @pytest.mark.parametrize("read_first", [False, True])
    def test_lazy_cpp_info_alias_and_replacement(self, read_first):
        conanfile = ConanFile(None)
        if read_first:
            assert conanfile.cpp_info is conanfile.cpp.package
            assert set(vars(conanfile.cpp)) == {"package"}
        replacement = CppInfo()
        replacement.libs = ["replacement"]
        conanfile.cpp_info = replacement
        assert conanfile.cpp_info is replacement
        assert conanfile.cpp.package is replacement
        assert conanfile.cpp_info.libs == ["replacement"]
        assert set(vars(conanfile.cpp)) == {"package"}

    def test_conanfile_naming_complete(self):
        client = TestClient()
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    pass
    def package_info(self):
        for member in Pkg.__dict__:
            if member.startswith('_') and not member.startswith("__"):
                assert(member.startswith('_conan'))
        for member in vars(self):
            if member.startswith('_') and not member.startswith("__"):
                assert(member.startswith('_conan'))
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkga --version=0.1 --user=user --channel=testing")
        client.save({"conanfile.py": conanfile.replace("pass",
                                                       "requires = 'pkga/0.1@user/testing'")})
        client.run("create . --name=pkgb --version=0.1 --user=user --channel=testing")
        client.save({"conanfile.py": conanfile.replace("pass",
                                                       "requires = 'pkgb/0.1@user/testing'")})
        client.run("create . --name=pkgc --version=0.1 --user=user --channel=testing")

    def test_conanfile_new_print(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            import sys
            class Pkg(ConanFile):
                def source(self):
                    print("Test1", file=sys.stderr)
                    print("Test2")
            """)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        assert "Test1" in client.stderr
        assert "Test2" in client.stderr
        assert "" == client.stdout

    def test_conanfile_new_print_save(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            import sys
            class Pkg(ConanFile):
                def source(self):
                    with open("myfile.txt", "w") as f:
                        print("Test1", file=f)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        assert "Test1" in client.load("myfile.txt")
