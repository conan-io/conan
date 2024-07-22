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
