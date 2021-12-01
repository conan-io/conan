import os
import textwrap

import pytest

from conans.client.profile_loader import _ProfileParser, ProfileLoader
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_profile_parser():
    txt = textwrap.dedent("""
        include(a/path/to\profile.txt)
        VAR=2
        include(other/path/to/file.txt)
        OTHERVAR=thing

        [settings]
        os=2
        """)
    a = _ProfileParser(txt)
    assert a.vars == {"VAR": "2", "OTHERVAR": "thing"}
    assert a.includes == ["a/path/to\profile.txt", "other/path/to/file.txt"]
    assert a.profile_text == textwrap.dedent("""[settings]
os=2""")

    txt = ""
    a = _ProfileParser(txt)
    assert a.vars == {}
    assert a.includes == []
    assert a.profile_text == ""

    txt = textwrap.dedent("""
        include(a/path/to\profile.txt)
        VAR=$REPLACE_VAR
        include(other/path/to/$FILE)
        OTHERVAR=thing

        [settings]
        os=$OTHERVAR
        """)

    a = _ProfileParser(txt)
    a.update_vars({"REPLACE_VAR": "22", "FILE": "MyFile", "OTHERVAR": "thing"})
    a.apply_vars()
    assert a.vars == {"VAR": "22", "OTHERVAR": "thing",
                      "REPLACE_VAR": "22", "FILE": "MyFile",}
    assert [i for i in a.get_includes()] == ["a/path/to\profile.txt", "other/path/to/MyFile"]
    assert a.profile_text == textwrap.dedent("""[settings]
os=thing""")

    txt = textwrap.dedent("""
        includes(a/path/to\profile.txt)
        """)

    with pytest.raises(ConanException):
        try:
            _ProfileParser(txt)
        except Exception as error:
            assert "Error while parsing line 1" in error.args[0]
            raise


def test_profiles_includes():
    tmp = temp_folder()

    def save_profile(txt, name):
        abs_profile_path = os.path.join(tmp, name)
        save(abs_profile_path, txt)

    os.mkdir(os.path.join(tmp, "subdir"))

    profile0 = textwrap.dedent("""
            ROOTVAR=0


            [tool_requires]
            one/1.$ROOTVAR@lasote/stable
            two/1.2@lasote/stable
        """)
    save_profile(profile0, "subdir/profile0.txt")

    profile1 = textwrap.dedent("""
            # Include in subdir, curdir
            MYVAR=1
            include(./profile0.txt)

            [settings]
            os=Windows
            [options]
            zlib:aoption=1
            zlib:otheroption=1
        """)

    save_profile(profile1, "subdir/profile1.txt")

    profile2 = textwrap.dedent("""
            #  Include in subdir
            include(./subdir/profile1.txt)
            [settings]
            os=$MYVAR
        """)

    save_profile(profile2, "profile2.txt")
    profile3 = textwrap.dedent("""
            OTHERVAR=34

            [tool_requires]
            one/1.5@lasote/stable
        """)

    save_profile(profile3, "profile3.txt")

    profile4 = textwrap.dedent("""
            include(./profile2.txt)
            include(./profile3.txt)

            [options]
            zlib:otheroption=12
        """)

    save_profile(profile4, "profile4.txt")

    profile_loader = ProfileLoader(cache=None)  # If not used cache, will not error
    profile = profile_loader.load_profile("./profile4.txt", tmp)

    assert profile.settings == {"os": "1"}
    assert profile.options["zlib"].aoption == 1
    assert profile.options["zlib"].otheroption == 12
    assert profile.tool_requires == {"*": [RecipeReference.loads("one/1.5@lasote/stable"),
                                                 RecipeReference.loads("two/1.2@lasote/stable")]}


def test_profile_include_order():
    tmp = temp_folder()

    save(os.path.join(tmp, "profile1.txt"), "MYVAR=fromProfile1")

    profile2 = textwrap.dedent("""
            include(./profile1.txt)
            MYVAR=fromProfile2
            [settings]
            os=$MYVAR
        """)
    save(os.path.join(tmp, "profile2.txt"), profile2)
    profile_loader = ProfileLoader(cache=None)  # If not used cache, will not error
    profile = profile_loader.load_profile("./profile2.txt", tmp)

    assert profile.settings["os"] == "fromProfile2"


def test_profile_load_absolute_path():
    """ When passing absolute path as profile file, it MUST be used.
        read_profile(/abs/path/profile, /abs, /.conan/profiles)
        /abs/path/profile MUST be consumed as target profile
    """
    current_profile_folder = temp_folder()
    current_profile_path = os.path.join(current_profile_folder, "default")
    save(current_profile_path, "[settings]\nos=Windows")

    profile_loader = ProfileLoader(cache=None)  # If not used cache, will not error
    profile = profile_loader.load_profile(current_profile_path)
    assert "Windows" == profile.settings["os"]


def test_profile_load_relative_path_dot():
    """ When passing relative ./path as profile file, it MUST be used
        read_profile(./profiles/profile, /tmp, /.conan/profiles)
        /tmp/profiles/profile MUST be consumed as target profile
    """
    current_profile_folder = temp_folder()
    current_profile_path = os.path.join(current_profile_folder, "profiles", "default")
    save(current_profile_path, "[settings]\nos=Windows")

    profile_loader = ProfileLoader(cache=None)  # If not used cache, will not error
    profile = profile_loader.load_profile("./profiles/default", current_profile_folder)
    assert "Windows" == profile.settings["os"]


def test_profile_load_relative_path_pardir():
    """ When passing relative ../path as profile file, it MUST be used
        read_profile(../profiles/profile, /tmp/current, /.conan/profiles)
        /tmp/profiles/profile MUST be consumed as target profile
    """
    tmp = temp_folder()
    current_profile_path = os.path.join(tmp, "profiles", "default")
    cwd = os.path.join(tmp, "user_folder")
    save(current_profile_path, "[settings]\nos=Windows")

    profile_loader = ProfileLoader(cache=None)  # If not used cache, will not error
    profile = profile_loader.load_profile("../profiles/default", cwd)
    assert "Windows" == profile.settings["os"]


def test_profile_buildenv():
    tmp = temp_folder()
    txt = textwrap.dedent("""
        [buildenv]
        MyVar1=My Value; 11
        MyVar1+=MyValue12
        MyPath1=(path)/some/path11
        MyPath1+=(path)/other path/path12
        """)
    current_profile_path = os.path.join(tmp, "default")
    save(current_profile_path, txt)

    profile_loader = ProfileLoader(cache=None)  # If not used cache, will not error
    profile = profile_loader.load_profile(current_profile_path)
    buildenv = profile.buildenv
    env = buildenv.get_profile_env(None)
    conanfile = ConanFileMock()
    env_vars = env.vars(conanfile)
    assert env_vars.get("MyVar1") == "My Value; 11 MyValue12"
    # Mock is never Windows path
    assert env_vars.get("MyPath1") == "/some/path11:/other path/path12"
