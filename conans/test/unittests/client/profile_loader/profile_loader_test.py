import os
import textwrap

import pytest

from conans.client.profile_loader import ProfileParser, read_profile
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.utils.mocks import ConanFileMock
from conans.test.utils.profiles import create_profile as _create_profile
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, save


def create_profile(folder, name, settings=None, package_settings=None, env=None,
                   package_env=None, options=None):
    _create_profile(folder, name, settings, package_settings, env, package_env, options)
    content = load(os.path.join(folder, name))
    content = "include(default)\n" + content
    save(os.path.join(folder, name), content)


def get_profile(folder, txt):
    abs_profile_path = os.path.join(folder, "Myprofile.txt")
    save(abs_profile_path, txt)
    return read_profile(abs_profile_path, None, None)


def test_profile_parser():
    txt = textwrap.dedent("""
        include(a/path/to\profile.txt)
        VAR=2
        include(other/path/to/file.txt)
        OTHERVAR=thing

        [settings]
        os=2
        """)
    a = ProfileParser(txt)
    assert a.vars == {"VAR": "2", "OTHERVAR": "thing"}
    assert a.includes == ["a/path/to\profile.txt", "other/path/to/file.txt"]
    assert a.profile_text == textwrap.dedent("""[settings]
os=2""")

    txt = ""
    a = ProfileParser(txt)
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

    a = ProfileParser(txt)
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
            ProfileParser(txt)
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


            [build_requires]
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

            [build_requires]
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

    profile, variables = read_profile("./profile4.txt", tmp, None)

    assert profile.settings == {"os": "1"}
    assert profile.options.as_list() == [('zlib:aoption', '1'), ('zlib:otheroption', '12')]
    assert profile.build_requires == {"*": [ConanFileReference.loads("one/1.5@lasote/stable"),
                                            ConanFileReference.loads("two/1.2@lasote/stable")]}


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
    profile, variables = read_profile("./profile2.txt", tmp, None)

    assert variables == {"MYVAR": "fromProfile2",
                         "PROFILE_DIR": tmp.replace('\\', '/')}
    assert profile.settings["os"] == "fromProfile2"


def test_profile_load_absolute_path():
    """ When passing absolute path as profile file, it MUST be used.
        read_profile(/abs/path/profile, /abs, /.conan/profiles)
        /abs/path/profile MUST be consumed as target profile
    """
    profile_name = "default"
    default_profile_folder = os.path.join(temp_folder(), "profiles")
    default_profile_path = os.path.join(default_profile_folder, profile_name)
    current_profile_folder = temp_folder()
    current_profile_path = os.path.join(current_profile_folder, profile_name)
    default_profile_content = textwrap.dedent("""
            [settings]
            BORSCHT=BEET SOUP
        """)
    current_profile_content = default_profile_content.replace("BEET", "RUSSIAN")

    save(default_profile_path, default_profile_content)
    save(current_profile_path, current_profile_content)

    profile, variables = read_profile(current_profile_path, current_profile_folder,
                                      default_profile_folder)
    assert "RUSSIAN SOUP" == profile.settings["BORSCHT"]
    assert current_profile_folder.replace("\\", "/") == variables["PROFILE_DIR"]


def test_profile_load_relative_path_dot():
    """ When passing relative ./path as profile file, it MUST be used
        read_profile(./profiles/profile, /tmp, /.conan/profiles)
        /tmp/profiles/profile MUST be consumed as target profile
    """
    profile_name = "default"
    default_profile_folder = os.path.join(temp_folder(), "profiles")
    default_profile_path = os.path.join(default_profile_folder, profile_name)
    current_profile_folder = temp_folder()
    current_profile_path = os.path.join(current_profile_folder, profile_name)
    default_profile_content = textwrap.dedent("""
            [settings]
            BORSCHT=BEET SOUP
        """)
    current_profile_content = default_profile_content.replace("BEET", "RUSSIAN")
    relative_current_profile_path = "." + os.path.join(os.sep,
                                                       os.path.basename(current_profile_folder),
                                                       profile_name)

    save(default_profile_path, default_profile_content)
    save(current_profile_path, current_profile_content)

    profile, variables = read_profile(relative_current_profile_path,
                                      os.path.dirname(current_profile_folder),
                                      default_profile_folder)
    assert "RUSSIAN SOUP" == profile.settings["BORSCHT"]
    assert current_profile_folder.replace("\\", "/") == variables["PROFILE_DIR"]


def test_profile_load_relative_path_pardir():
    """ When passing relative ../path as profile file, it MUST be used
        read_profile(../profiles/profile, /tmp/current, /.conan/profiles)
        /tmp/profiles/profile MUST be consumed as target profile
    """
    profile_name = "default"
    default_profile_folder = os.path.join(temp_folder(), "profiles")
    os.mkdir(default_profile_folder)
    default_profile_path = os.path.join(default_profile_folder, profile_name)

    current_temp_folder = temp_folder()
    current_profile_folder = os.path.join(current_temp_folder, "profiles")
    current_running_folder = os.path.join(current_temp_folder, "current")

    os.mkdir(current_profile_folder)
    os.mkdir(current_running_folder)

    current_profile_path = os.path.join(current_profile_folder, profile_name)
    default_profile_content = textwrap.dedent("""
            [settings]
            BORSCHT=BEET SOUP
        """)
    current_profile_content = default_profile_content.replace("BEET", "RUSSIAN")
    relative_current_profile_path = os.pardir + os.path.join(os.sep, "profiles", profile_name)

    save(default_profile_path, default_profile_content)
    save(current_profile_path, current_profile_content)

    profile, variables = read_profile(relative_current_profile_path,
                                      current_running_folder,
                                      default_profile_folder)
    assert "RUSSIAN SOUP" == profile.settings["BORSCHT"]
    assert current_profile_folder.replace("\\", "/") == variables["PROFILE_DIR"]


def test_profile_buildenv():
    tmp = temp_folder()
    txt = textwrap.dedent("""
        [buildenv]
        MyVar1=My Value; 11
        MyVar1+=MyValue12
        MyPath1=(path)/some/path11
        MyPath1+=(path)/other path/path12
        """)
    profile, _ = get_profile(tmp, txt)
    buildenv = profile.buildenv
    env = buildenv.get_profile_env(None)
    conanfile = ConanFileMock()
    env_vars = env.vars(conanfile)
    assert env_vars.get("MyVar1") == "My Value; 11 MyValue12"
    # Mock is never Windows path
    assert env_vars.get("MyPath1") == "/some/path11:/other path/path12"
