import os
import textwrap

import pytest

from conan.internal.api.profile.profile_loader import _ProfileParser, ProfileLoader
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conan.test.utils.mocks import ConanFileMock, MockSettings
from conan.test.utils.test_files import temp_folder
from conans.util.files import save


def test_profile_parser():
    txt = textwrap.dedent(r"""
        include(a/path/to\profile.txt)
        include(other/path/to/file.txt)

        [settings]
        os=2
        """)
    a = _ProfileParser(txt)
    assert a.includes == [r"a/path/to\profile.txt", "other/path/to/file.txt"]
    assert a.profile_text == textwrap.dedent("""[settings]
os=2""")

    txt = ""
    a = _ProfileParser(txt)
    assert a.includes == []
    assert a.profile_text == ""

    txt = textwrap.dedent(r"""
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
            {% set ROOTVAR=0 %}


            [tool_requires]
            one/1.{{ROOTVAR}}@lasote/stable
            two/1.2@lasote/stable
        """)
    save_profile(profile0, "subdir/profile0.txt")

    profile1 = textwrap.dedent("""
            # Include in subdir, curdir
            include(./profile0.txt)

            [settings]
            os=Windows
            [options]
            zlib*:aoption=1
            zlib*:otheroption=1
        """)

    save_profile(profile1, "subdir/profile1.txt")

    profile2 = textwrap.dedent("""
            #  Include in subdir
            {% set MYVAR=1 %}
            include(./subdir/profile1.txt)
            [settings]
            os={{MYVAR}}
        """)

    save_profile(profile2, "profile2.txt")
    profile3 = textwrap.dedent("""
            [tool_requires]
            one/1.5@lasote/stable
        """)

    save_profile(profile3, "profile3.txt")

    profile4 = textwrap.dedent("""
            include(./profile2.txt)
            include(./profile3.txt)

            [options]
            zlib*:otheroption=12
        """)

    save_profile(profile4, "profile4.txt")

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
    profile = profile_loader.load_profile("./profile4.txt", tmp)

    assert profile.settings == {"os": "1"}
    assert profile.options["zlib*"].aoption == 1
    assert profile.options["zlib*"].otheroption == 12
    assert profile.tool_requires == {"*": [RecipeReference.loads("one/1.5@lasote/stable"),
                                           RecipeReference.loads("two/1.2@lasote/stable")]}


def test_profile_compose_platform_tool_requires():
    tmp = temp_folder()
    save(os.path.join(tmp, "profile0"), "[platform_tool_requires]\ntool1/1.0")
    save(os.path.join(tmp, "profile1"), "[platform_tool_requires]\ntool2/2.0")
    save(os.path.join(tmp, "profile2"), "include(./profile0)\n[platform_tool_requires]\ntool3/3.0")
    save(os.path.join(tmp, "profile3"), "include(./profile0)\n[platform_tool_requires]\ntool1/1.1")

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
    profile2 = profile_loader.load_profile("./profile2", tmp)
    assert profile2.platform_tool_requires == [RecipeReference.loads("tool1/1.0"),
                                               RecipeReference.loads("tool3/3.0")]
    profile3 = profile_loader.load_profile("./profile3", tmp)
    assert profile3.platform_tool_requires == [RecipeReference.loads("tool1/1.1")]
    profile0 = profile_loader.load_profile("./profile0", tmp)
    profile1 = profile_loader.load_profile("./profile1", tmp)
    profile0.compose_profile(profile1)
    assert profile0.platform_tool_requires == [RecipeReference.loads("tool1/1.0"),
                                               RecipeReference.loads("tool2/2.0")]


def test_profile_compose_tool_requires():
    tmp = temp_folder()
    save(os.path.join(tmp, "profile0"), "[tool_requires]\ntool1/1.0")
    save(os.path.join(tmp, "profile1"), "[tool_requires]\ntool2/2.0")
    save(os.path.join(tmp, "profile2"), "include(./profile0)\n[tool_requires]\ntool3/3.0")
    save(os.path.join(tmp, "profile3"), "include(./profile0)\n[tool_requires]\ntool1/1.1")

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
    profile2 = profile_loader.load_profile("./profile2", tmp)
    assert profile2.tool_requires == {"*": [RecipeReference.loads("tool1/1.0"),
                                            RecipeReference.loads("tool3/3.0")]}
    profile3 = profile_loader.load_profile("./profile3", tmp)
    assert profile3.tool_requires == {"*": [RecipeReference.loads("tool1/1.1")]}

    profile0 = profile_loader.load_profile("./profile0", tmp)
    profile1 = profile_loader.load_profile("./profile1", tmp)
    profile0.compose_profile(profile1)
    assert profile0.tool_requires == {"*": [RecipeReference.loads("tool1/1.0"),
                                            RecipeReference.loads("tool2/2.0")]}


def test_profile_include_order():
    tmp = temp_folder()

    save(os.path.join(tmp, "profile1.txt"), '{% set MYVAR="fromProfile1" %}')

    profile2 = textwrap.dedent("""
            include(./profile1.txt)
            {% set MYVAR="fromProfile2" %}
            [settings]
            os={{MYVAR}}
        """)
    save(os.path.join(tmp, "profile2.txt"), profile2)
    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
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

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
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

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
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

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
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

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error
    profile = profile_loader.load_profile(current_profile_path)
    buildenv = profile.buildenv
    env = buildenv.get_profile_env(None)
    conanfile = ConanFileMock()
    conanfile.settings_build = MockSettings({"os": "Linux", "arch": "x86_64"})
    env_vars = env.vars(conanfile)
    assert env_vars.get("MyVar1") == "My Value; 11 MyValue12"
    assert env_vars.get("MyPath1") == "/some/path11:/other path/path12"

    conanfile.settings_build = MockSettings({"os": "Windows", "arch": "x86_64"})
    env_vars = env.vars(conanfile)
    assert env_vars.get("MyPath1") == "/some/path11;/other path/path12"


@pytest.mark.parametrize("conf_name", [
    "core.gzip:compresslevel=5",
    "core.gzip:compresslevel"
])
def test_profile_core_confs_error(conf_name):
    tmp = temp_folder()
    current_profile_path = os.path.join(tmp, "default")
    save(current_profile_path, "")

    profile_loader = ProfileLoader(cache_folder=temp_folder())  # If not used cache, will not error

    with pytest.raises(ConanException) as exc:
        profile_loader.from_cli_args([], [], [], [conf_name], None)
    assert "[conf] 'core.*' configurations are not allowed in profiles" in str(exc.value)
