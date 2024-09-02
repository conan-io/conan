import os
import textwrap

from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_profile_local_folder_priority_cache():
    """ includes or args without "./" will resolve to the cache first
    """
    c = TestClient()
    c.save({"profiles/default": f"include(otherprofile)",
            "profiles/otherprofile": "[settings]\nos=AIX",
            "conanfile.txt": ""})
    save(os.path.join(c.cache.profiles_path, "otherprofile"), "[settings]\nos=FreeBSD")

    # Must use local path, otherwise look for it in the cache
    c.run("install . -pr=./profiles/default")
    assert "os=FreeBSD" in c.out


def test_profile_local_folder_priority_relative():
    """ The local include(./profile) must have priority over a file with same name in cache
    """
    c = TestClient()
    c.save({"profiles/default": f"include(./otherprofile)",
            "profiles/otherprofile": "[settings]\nos=AIX",
            "conanfile.txt": ""})
    save(os.path.join(c.cache.profiles_path, "otherprofile"), "[settings]\nos=FreeBSD")

    # Must use local path, otherwise look for it in the cache
    c.run("install . -pr=./profiles/default")
    assert "os=AIX" in c.out


def test_profile_cache_folder_priority():
    """ The cache include(./profile) must have priority over a file with same name in local
    """
    c = TestClient()
    c.save({"otherprofile": "[settings]\nos=FreeBSD",
            "conanfile.txt": ""})
    save(os.path.join(c.cache.profiles_path, "default"), "include(./otherprofile)")
    save(os.path.join(c.cache.profiles_path, "otherprofile"), "[settings]\nos=AIX")

    c.run("install . -pr=default")
    assert "os=AIX" in c.out


def test_profile_cli_priority():
    c = TestClient()
    profile1 = textwrap.dedent("""\
        [settings]
        os=AIX
        [conf]
        user.myconf:myvalue1=1
        user.myconf:myvalue2=[2]
        user.myconf:myvalue3={"3": "4", "a": "b"}
        user.myconf:myvalue4={"1": "2"}
        user.myconf:myvalue5={"6": "7"}
        """)
    profile2 = textwrap.dedent("""\
        [settings]
        os=FreeBSD
        [conf]
        user.myconf:myvalue1=2
        user.myconf:myvalue2+=4
        user.myconf:myvalue3*={"3": "5"}
        user.myconf:myvalue5={"6": "7"}
        """)
    c.save({"profile1": profile1,
            "profile2": profile2})
    c.run("profile show -pr=./profile1 -pr=./profile2")
    assert "os=FreeBSD" in c.out
    assert "user.myconf:myvalue1=2" in c.out
    assert "user.myconf:myvalue2=[2, 4]" in c.out
    assert "user.myconf:myvalue3={'3': '5', 'a': 'b'}" in c.out
    assert "user.myconf:myvalue4={'1': '2'}" in c.out
    assert "user.myconf:myvalue5={'6': '7'}" in c.out


def test_profiles_patterns_include():
    # https://github.com/conan-io/conan/issues/16718
    c = TestClient()
    msvc = textwrap.dedent("""
        [settings]
        compiler=msvc
        compiler.cppstd=14
        compiler.version=193
        os=Windows

        test*/*:compiler.cppstd=14
        """)
    clang = textwrap.dedent("""
        include(./msvc)
        [settings]
        test*/*:compiler=clang
        test*/*:compiler.cppstd=17
        test*/*:compiler.runtime_version=v144
        test*/*:compiler.version=18
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "test_pkg"
            version = "0.1"
            settings = "os", "compiler"
            def generate(self):
                self.output.info(f"MyCompiler={self.settings.compiler}!!!")
                self.output.info(f"MyCompilerVersion={self.settings.compiler.version}!!!")
                self.output.info(f"MyCompilerCpp={self.settings.compiler.cppstd}!!!")
            """)
    c.save({"conanfile.py": conanfile,
            "msvc": msvc,
            "clang": clang})
    c.run("install . -pr=clang")
    assert "conanfile.py (test_pkg/0.1): MyCompiler=clang!!!" in c.out
    assert "conanfile.py (test_pkg/0.1): MyCompilerVersion=18!!!" in c.out
    assert "conanfile.py (test_pkg/0.1): MyCompilerCpp=17!!!" in c.out
