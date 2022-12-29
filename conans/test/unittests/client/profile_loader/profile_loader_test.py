import os
import textwrap
import pytest

from conans.client.profile_loader import ProfileParser, read_profile
from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.model.profile import Profile
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


def test_profile_loads():

    tmp = temp_folder()

    prof = textwrap.dedent("""
        [env]
        CXX_FLAGS="-DAAA=0"
        [settings]
    """)
    new_profile, _ = get_profile(tmp, prof)
    assert new_profile.env_values.env_dicts("") == ({'CXX_FLAGS': '-DAAA=0'}, {})

    prof = textwrap.dedent("""
        [env]
        CXX_FLAGS="-DAAA=0"
        MyPackage:VAR=1
        MyPackage:OTHER=2
        OtherPackage:ONE=ONE
        [settings]
    """)
    new_profile, _ = get_profile(tmp, prof)
    assert new_profile.env_values.env_dicts("") == ({'CXX_FLAGS': '-DAAA=0'}, {})
    assert new_profile.env_values.env_dicts("MyPackage") == ({"OTHER": "2",
                                                              "VAR": "1",
                                                              "CXX_FLAGS": "-DAAA=0"}, {})

    assert new_profile.env_values.env_dicts("OtherPackage") == ({'CXX_FLAGS': '-DAAA=0',
                                                                 'ONE': 'ONE'}, {})

    prof = textwrap.dedent("""
            [env]
            CXX_FLAGS='-DAAA=0'
            [settings]
        """)
    new_profile, _ = get_profile(tmp, prof)
    assert new_profile.env_values.env_dicts("") == ({'CXX_FLAGS': '-DAAA=0'}, {})

    prof = textwrap.dedent("""
            [env]
            CXX_FLAGS=-DAAA=0
            [settings]
        """)
    new_profile, _ = get_profile(tmp, prof)
    assert new_profile.env_values.env_dicts("") == ({'CXX_FLAGS': '-DAAA=0'}, {})

    prof = textwrap.dedent("""
            [env]
            CXX_FLAGS="-DAAA=0
            [settings]
        """)
    new_profile, _ = get_profile(tmp, prof)
    assert new_profile.env_values.env_dicts("") == ({'CXX_FLAGS': '"-DAAA=0'}, {})

    prof = textwrap.dedent("""
            [settings]
            zlib:compiler=gcc
            compiler=Visual Studio
        """)
    new_profile, _ = get_profile(tmp, prof)
    assert new_profile.package_settings["zlib"] == {"compiler": "gcc"}
    assert new_profile.settings["compiler"] == "Visual Studio"


def test_profile_empty_env():
    tmp = temp_folder()
    profile, _ = get_profile(tmp, "")
    assert isinstance(profile.env_values, EnvValues)


def test_profile_empty_env_settings():
    tmp = temp_folder()
    profile, _ = get_profile(tmp, "[settings]")
    assert isinstance(profile.env_values, EnvValues)


def test_profile_loads_win():
    tmp = temp_folder()
    prof = textwrap.dedent("""
            [env]
            QTPATH=C:/QtCommercial/5.8/msvc2015_64/bin
            QTPATH2="C:/QtCommercial2/5.8/msvc2015_64/bin"
        """)
    new_profile, _ = get_profile(tmp, prof)
    assert new_profile.env_values.data[None]["QTPATH"] == "C:/QtCommercial/5.8/msvc2015_64/bin"
    assert new_profile.env_values.data[None]["QTPATH2"] == "C:/QtCommercial2/5.8/msvc2015_64/bin"
    assert "QTPATH=C:/QtCommercial/5.8/msvc2015_64/bin" in new_profile.dumps()
    assert "QTPATH2=C:/QtCommercial2/5.8/msvc2015_64/bin" in new_profile.dumps()


def test_profile_load_dump():
    # Empty profile
    tmp = temp_folder()
    profile = Profile()
    dumps = profile.dumps()
    new_profile, _ = get_profile(tmp, dumps)
    assert new_profile.settings == profile.settings

    # Settings
    profile = Profile()
    profile.settings["arch"] = "x86_64"
    profile.settings["compiler"] = "Visual Studio"
    profile.settings["compiler.version"] = "12"

    profile.env_values.add("CXX", "path/to/my/compiler/g++")
    profile.env_values.add("CC", "path/to/my/compiler/gcc")

    profile.build_requires["*"] = ["android_toolchain/1.2.8@lasote/testing"]
    profile.build_requires["zlib/*"] = ["cmake/1.0.2@lasote/stable",
                                        "autotools/1.0.3@lasote/stable"]

    dump = profile.dumps()
    new_profile, _ = get_profile(tmp, dump)
    assert new_profile.settings == profile.settings
    assert new_profile.settings["arch"] == "x86_64"
    assert new_profile.settings["compiler.version"] == "12"
    assert new_profile.settings["compiler"] == "Visual Studio"

    assert new_profile.env_values.env_dicts("") == ({'CXX': 'path/to/my/compiler/g++',
                                                     'CC': 'path/to/my/compiler/gcc'}, {})

    assert new_profile.build_requires["zlib/*"] == \
           [ConanFileReference.loads("cmake/1.0.2@lasote/stable"),
            ConanFileReference.loads("autotools/1.0.3@lasote/stable")]
    assert new_profile.build_requires["*"] == \
           [ConanFileReference.loads("android_toolchain/1.2.8@lasote/testing")]


def test_profile_vars():
    tmp = temp_folder()

    txt = textwrap.dedent("""
            MY_MAGIC_VAR=The owls are not

            [env]
            MYVAR=$MY_MAGIC_VAR what they seem.
        """)
    profile, _ = get_profile(tmp, txt)
    assert "The owls are not what they seem." == profile.env_values.data[None]["MYVAR"]

    # Order in replacement, variable names (simplification of preprocessor)
    txt = textwrap.dedent("""
            P=Diane, the coffee at the Great Northern
            P2=is delicious

            [env]
            MYVAR=$P2
        """)
    profile, _ = get_profile(tmp, txt)
    assert "Diane, the coffee at the Great Northern2" == profile.env_values.data[None]["MYVAR"]

    # Variables without spaces
    txt = textwrap.dedent("""
            VARIABLE WITH SPACES=12
            [env]
            MYVAR=$VARIABLE WITH SPACES
        """)
    with pytest.raises(ConanException) as conan_error:
        get_profile(tmp, txt)
        assert "The names of the variables cannot contain spaces" in str(conan_error.value)


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
            [env]
            package1:ENVY=$MYVAR
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

            [env]
            MYVAR=FromProfile3And$OTHERVAR

            [options]
            zlib:otheroption=12
        """)

    save_profile(profile4, "profile4.txt")

    profile, variables = read_profile("./profile4.txt", tmp, None)

    assert variables == {"MYVAR": "1",
                         "OTHERVAR": "34",
                         "PROFILE_DIR": tmp.replace('\\', '/'),
                         "ROOTVAR": "0"}
    assert "FromProfile3And34" == profile.env_values.data[None]["MYVAR"]
    assert "1" == profile.env_values.data["package1"]["ENVY"]
    assert profile.settings == {"os": "1"}
    assert profile.options.as_list() == [('zlib:aoption', '1'), ('zlib:otheroption', '12')]
    assert profile.build_requires == {"*": [ConanFileReference.loads("one/1.5@lasote/stable"),
                                            ConanFileReference.loads("two/1.2@lasote/stable")]}


def test_profile_dir():
    tmp = temp_folder()
    txt = textwrap.dedent("""
            [env]
            PYTHONPATH=$PROFILE_DIR/my_python_tools
        """)

    def assert_path(profile):
        pythonpath = profile.env_values.env_dicts("")[0]["PYTHONPATH"]
        assert pythonpath == os.path.join(tmp, "my_python_tools").replace('\\', '/')

    abs_profile_path = os.path.join(tmp, "Myprofile.txt")
    save(abs_profile_path, txt)
    profile, _ = read_profile(abs_profile_path, None, None)
    assert_path(profile)

    profile, _ = read_profile("./Myprofile.txt", tmp, None)
    assert_path(profile)

    profile, _ = read_profile("Myprofile.txt", None, tmp)
    assert_path(profile)


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
            [env]
            BORSCHT=BEET SOUP
        """)
    current_profile_content = default_profile_content.replace("BEET", "RUSSIAN")

    save(default_profile_path, default_profile_content)
    save(current_profile_path, current_profile_content)

    profile, variables = read_profile(current_profile_path, current_profile_folder,
                                      default_profile_folder)
    assert ({"BORSCHT": "RUSSIAN SOUP"}, {}) == profile.env_values.env_dicts("")
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
            [env]
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
    assert ({"BORSCHT": "RUSSIAN SOUP"}, {}) == profile.env_values.env_dicts("")
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
            [env]
            BORSCHT=BEET SOUP
        """)
    current_profile_content = default_profile_content.replace("BEET", "RUSSIAN")
    relative_current_profile_path = os.pardir + os.path.join(os.sep, "profiles", profile_name)

    save(default_profile_path, default_profile_content)
    save(current_profile_path, current_profile_content)

    profile, variables = read_profile(relative_current_profile_path,
                                      current_running_folder,
                                      default_profile_folder)
    assert ({"BORSCHT": "RUSSIAN SOUP"}, {}) == profile.env_values.env_dicts("")
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
    assert env_vars.get("MyPath1") == "/some/path11{}/other path/path12".format(os.pathsep)


def test_profile_tool_requires():
    tmp = temp_folder()
    txt = textwrap.dedent("""
        [tool_requires]
        tool/0.1
        """)
    profile, _ = get_profile(tmp, txt)
    assert profile.build_requires["*"] == [ConanFileReference.loads("tool/0.1")]
