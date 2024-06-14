import json
import os
import platform
import textwrap
import unittest
from collections import OrderedDict
from textwrap import dedent

import pytest
from parameterized import parameterized

from conan.internal.paths import CONANFILE
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.profiles import create_profile as _create_profile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import load, save

conanfile_scope_env = """
from conan import ConanFile

class AConan(ConanFile):
    name = "hello0"
    version = "0.1"
    settings = "os", "compiler", "arch"

    def build(self):
        # Print environment vars
        if self.settings.os == "Windows":
            self.run("SET")
        else:
            self.run("env")
"""


def create_profile(folder, name, settings=None, package_settings=None, env=None,
                   package_env=None, options=None):
    _create_profile(folder, name, settings, package_settings, env, package_env, options)
    content = load(os.path.join(folder, name))
    content = "include(default)\n    \n" + content
    save(os.path.join(folder, name), content)


class ProfileTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def test_profile_relative_cwd(self):
        self.client.save({"conanfile.txt": "", "sub/sub/profile": ""})
        self.client.current_folder = os.path.join(self.client.current_folder, "sub")
        self.client.run("install .. -pr=sub/profile2", assert_error=True)
        self.assertIn("ERROR: Profile not found: sub/profile2", self.client.out)
        self.client.run("install .. -pr=sub/profile")
        self.assertIn("Installing packages", self.client.out)

    def test_bad_syntax(self):
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run("export . --user=lasote --channel=stable")

        profile = '''
        [settings
        '''
        clang_profile_path = os.path.join(self.client.cache.profiles_path, "clang")
        save(clang_profile_path, profile)
        self.client.run("install --requires=hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        self.assertIn("Error reading 'clang' profile", self.client.out)
        self.assertIn("Bad syntax", self.client.out)

        profile = '''
        [settings]
        [invented]
        '''
        save(clang_profile_path, profile)
        self.client.run("install --requires=hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        self.assertIn("Unrecognized field 'invented'", self.client.out)
        self.assertIn("Error reading 'clang' profile", self.client.out)

        profile = '''
        [settings]
        as
        '''
        save(clang_profile_path, profile)
        self.client.run("install --requires=hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        self.assertIn("Error reading 'clang' profile: Invalid setting line 'as'",
                      self.client.out)

        profile = '''
        [settings]
        os =   a value
        '''
        save(clang_profile_path, profile)
        self.client.run("install --requires=hello0/0.1@lasote/stable --build missing -pr clang",
                        assert_error=True)
        # stripped "a value"
        self.assertIn("'a value' is not a valid 'settings.os'", self.client.out)

    @parameterized.expand([("", ), ("./local_profiles/", ), (None, )])
    def test_install_with_missing_profile(self, path):
        if path is None:
            # Not good practice to introduce temp_folder() in the expand because it randomize
            # the test names causing issues to split them in N processes
            path = temp_folder() + "/"
        self.client.save({CONANFILE: conanfile_scope_env})
        self.client.run('install . -pr "%sscopes_env"' % path, assert_error=True)
        self.assertIn("ERROR: Profile not found:", self.client.out)
        self.assertIn("scopes_env", self.client.out)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Windows profiles")
    def test_install_profile_settings(self):
        # Create a profile and use it
        profile_settings = OrderedDict([("compiler", "msvc"),
                                        ("compiler.version", "191"),
                                        ("compiler.runtime", "dynamic"),
                                        ("arch", "x86")])

        create_profile(self.client.cache.profiles_path, "vs_12_86",
                       settings=profile_settings, package_settings={})

        self.client.save({"conanfile.py": conanfile_scope_env})
        self.client.run("export . --user=lasote --channel=stable")
        self.client.run("install . --build missing -pr vs_12_86")
        info = self.client.out
        for setting, value in profile_settings.items():
            self.assertIn("%s=%s" % (setting, value), info)

        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86 -s compiler.version=191")
        info = self.client.out
        for setting, value in profile_settings.items():
            if setting != "compiler.version":
                self.assertIn("%s=%s" % (setting, value), info)
            else:
                self.assertIn("compiler.version=191", info)

        # Use package settings in profile
        tmp_settings = OrderedDict()
        tmp_settings["compiler"] = "gcc"
        tmp_settings["compiler.libcxx"] = "libstdc++11"
        tmp_settings["compiler.version"] = "4.8"
        package_settings = {"hello0/*": tmp_settings}
        create_profile(self.client.cache.profiles_path,
                       "vs_12_86_hello0_gcc", settings=profile_settings,
                       package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_hello0_gcc -s compiler.version=191")
        info = self.client.out
        self.assertIn("compiler=gcc", info)
        self.assertIn("compiler.libcxx=libstdc++11", info)

        # If other package is specified compiler is not modified
        package_settings = {"NoExistsRecipe": tmp_settings}
        create_profile(self.client.cache.profiles_path,
                       "vs_12_86_hello0_gcc", settings=profile_settings,
                       package_settings=package_settings)

        # Mix command line package settings with profile
        package_settings = {"hello0/*": tmp_settings}
        create_profile(self.client.cache.profiles_path, "vs_12_86_hello0_gcc",
                       settings=profile_settings, package_settings=package_settings)

        # Try to override some settings in install command
        self.client.run("install . --build missing -pr vs_12_86_hello0_gcc"
                        " -s compiler.version=191 -s hello0/*:compiler.libcxx=libstdc++")
        info = self.client.out
        self.assertIn("compiler=gcc", info)
        self.assertNotIn("compiler.libcxx=libstdc++11", info)
        self.assertIn("compiler.libcxx=libstdc++", info)

    def test_install_profile_package_settings(self):

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class HelloConan(ConanFile):
                name = 'hello0'
                version = '0.1'
                settings = "os", "compiler", "arch", "build_type"
                def configure(self):
                    self.output.info(self.settings.compiler)
                    self.output.info(self.settings.compiler.version)
            """)
        self.client.save({"conanfile.py": conanfile})

        # Create a profile and use it
        profile_settings = OrderedDict([("os", "Windows"),
                                        ("compiler", "msvc"),
                                        ("compiler.version", "191"),
                                        ("compiler.runtime", "dynamic"),
                                        ("arch", "x86")])

        # Use package settings in profile
        tmp_settings = OrderedDict()
        tmp_settings["compiler"] = "gcc"
        tmp_settings["compiler.libcxx"] = "libstdc++11"
        tmp_settings["compiler.version"] = "4.8"
        package_settings = {"*@lasote/*": tmp_settings}
        _create_profile(self.client.cache.profiles_path,
                        "myprofile", settings=profile_settings,
                        package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . --user=lasote --channel=testing -pr myprofile")
        info = self.client.out
        self.assertIn("(hello0/0.1@lasote/testing): gcc", info)
        self.assertIn("(hello0/0.1@lasote/testing): 4.8", info)

        package_settings = {"*@other/*": tmp_settings}
        _create_profile(self.client.cache.profiles_path,
                        "myprofile", settings=profile_settings,
                        package_settings=package_settings)
        # Try to override some settings in install command
        self.client.run("install . --user=lasote --channel=testing -pr myprofile")
        info = self.client.out
        self.assertIn("(hello0/0.1@lasote/testing): msvc", info)
        self.assertIn("(hello0/0.1@lasote/testing): 191", info)
        self.assertNotIn("(hello0/0.1@lasote/testing): gcc", info)
        self.assertNotIn("(hello0/0.1@lasote/testing): 4.8", info)

    def test_package_settings_no_user_channel(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                settings = "os"
                def build(self):
                    self.output.info("SETTINGS! os={}!!".format(self.settings.os))
                """)
        profile = textwrap.dedent("""
            [settings]
            os=Windows
            # THIS FAILED BEFORE WITH NO MATCH
            mypkg/0.1:os=Linux
            mypkg/0.1@user/channel:os=FreeBSD
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "profile": profile})

        client.run("create . --name=mypkg --version=0.1 --user=user --channel=channel -pr=profile")
        assert "mypkg/0.1@user/channel: SETTINGS! os=FreeBSD!!" in client.out
        client.run("create . --name=mypkg --version=0.1 -pr=profile")
        assert "mypkg/0.1: SETTINGS! os=Linux!!" in client.out

    def test_install_profile_options(self):
        create_profile(self.client.cache.profiles_path, "vs_12_86",
                       options={"hello0*:language": 1,
                                "hello0*:static": False})

        self.client.save({"conanfile.py": GenConanfile("hello0", "1").with_option("language", [1, 2])
                          .with_option("static", [True, False])})
        self.client.run("install . --build missing -pr vs_12_86")
        info = self.client.out
        self.assertIn("language=1", info)
        self.assertIn("static=False", info)

    def test_scopes_env(self):
        # Create a profile and use it
        c = TestClient()
        c.save({"profile": "include(default)\n[buildenv]\nCXX=/path/tomy/g++",
                "conanfile.py": conanfile_scope_env})

        c.run("build . -pr=profile")
        assert "CXX=/path/tomy/g++" in c.out

        # The env variable shouldn't persist after install command
        assert os.environ.get("CC", None) != "/path/tomy/gcc"
        assert os.environ.get("CXX", None) != "/path/tomy/g++"

    def test_info_with_profiles(self):

        self.client.run("remove '*' -c")
        # Create a simple recipe to require
        winreq_conanfile = '''
from conans.model.conan_file import ConanFile

class winrequireDefaultNameConan(ConanFile):
    name = "winrequire"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"

'''

        files = {"conanfile.py": winreq_conanfile}
        self.client.save(files)
        self.client.run("export . --user=lasote --channel=stable")

        # Now require the first recipe depending on OS=windows
        conanfile = '''from conans.model.conan_file import ConanFile
import os

class DefaultNameConan(ConanFile):
    name = "hello"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"

    def requirements(self):
        if self.settings.os == "Windows":
            self.requires("winrequire/0.1@lasote/stable")

'''
        files = {"conanfile.py": conanfile}
        self.client.save(files)
        self.client.run("export . --user=lasote --channel=stable")

        # Create a profile that doesn't activate the require
        create_profile(self.client.cache.profiles_path, "scopes_env",
                       settings={"os": "Linux"})

        # Install with the previous profile
        self.client.run("graph info --requires=hello/0.1@lasote/stable --profile scopes_env")
        self.assertNotIn('''Requires:
                winrequire/0.1@lasote/stable''', self.client.out)

        # Create a profile that activate the require
        create_profile(self.client.cache.profiles_path, "scopes_env",
                       settings={"os": "Windows"})

        # Install with the previous profile
        self.client.run("graph info --requires=hello/0.1@lasote/stable --profile scopes_env")
        self.assertIn(' winrequire/0.1@lasote/stable', self.client.out)


class ProfileAggregationTest(unittest.TestCase):

    profile1 = dedent("""
    [settings]
    os=Windows
    arch=x86_64
    """)

    profile2 = dedent("""
    [settings]
    arch=x86
    build_type=Debug
    compiler=msvc
    compiler.version=191
    compiler.runtime=dynamic
    """)

    conanfile = dedent("""
    from conans.model.conan_file import ConanFile
    import os

    class DefaultNameConan(ConanFile):
        settings = "os", "compiler", "arch", "build_type"

        def build(self):
            self.output.warning("ENV1:%s" % os.getenv("ENV1"))
            self.output.warning("ENV2:%s" % os.getenv("ENV2"))
            self.output.warning("ENV3:%s" % os.getenv("ENV3"))
    """)

    consumer = dedent("""
    from conans.model.conan_file import ConanFile
    import os

    class DefaultNameConan(ConanFile):
        settings = "os", "compiler", "arch", "build_type"
        requires = "lib/1.0@user/channel"
    """)

    def setUp(self):
        self.client = TestClient()
        self.client.save({CONANFILE: self.conanfile,
                          "profile1": self.profile1, "profile2": self.profile2})
        self._pkg_lib_10_id = "9b7f1e80c96289e8d9a3e7ded02830525090d5d4"

    def test_info(self):
        # The latest declared profile has priority
        self.client.run("create . --name=lib --version=1.0 --user=user --channel=channel --profile profile1 -pr profile2")

        self.client.save({CONANFILE: self.consumer})
        self.client.run("graph info . --profile profile1 --profile profile2")
        self.assertIn(self._pkg_lib_10_id, self.client.out)

    def test_export_pkg(self):
        self.client.run("export-pkg . --name=lib --version=1.0 --user=user --channel=channel -pr profile1 -pr profile2")
        # ID for the expected settings applied: x86, Visual Studio 15,...
        self.assertIn(self._pkg_lib_10_id, self.client.out)

    def test_profile_crazy_inheritance(self):
        profile1 = dedent("""
            [settings]
            os=Windows
            arch=x86_64
            compiler=msvc
            compiler.version=191
            compiler.runtime=dynamic
            """)

        profile2 = dedent("""
            include(profile1)
            [settings]
            os=Linux
            """)

        self.client.save({"profile1": profile1, "profile2": profile2})
        self.client.run("create . --name=lib --version=1.0 --profile profile2 -pr profile1")
        self.assertIn(dedent("""\
                             [settings]
                             arch=x86_64
                             compiler=msvc
                             compiler.runtime=dynamic
                             compiler.runtime_type=Release
                             compiler.version=191
                             os=Windows"""), self.client.out)


def test_profile_from_cache_path():
    """ When passing relative folder/profile as profile file, it MUST be used
        conan install . -pr=profiles/default
        /tmp/profiles/default MUST be consumed as target profile
        https://github.com/conan-io/conan/pull/8685
    """
    client = TestClient()
    path = os.path.join(client.cache.profiles_path, "android", "profile1")
    save(path, "[settings]\nos=Android")
    client.save({"conanfile.txt": ""})
    client.run("install . -pr=android/profile1")
    assert "os=Android" in client.out


def test_profile_from_relative_pardir():
    """ When passing relative ../path as profile file, it MUST be used
        conan install . -pr=../profiles/default
        /tmp/profiles/default MUST be consumed as target profile
    """
    client = TestClient()
    client.save({"profiles/default": "[settings]\nos=AIX",
                 "current/conanfile.txt": ""})
    with client.chdir("current"):
        client.run("install . -pr=../profiles/default")
    assert "os=AIX" in client.out


def test_profile_from_relative_dotdir():
    """ When passing relative ./path as profile file, it MUST be used
        conan install . -pr=./profiles/default
        /tmp/profiles/default MUST be consumed as target profile
    """
    client = TestClient()
    client.save({os.path.join("profiles", "default"): "[settings]\nos=AIX",
                 os.path.join("current", "conanfile.txt"): ""})
    client.run("install ./current -pr=./profiles/default")
    assert "os=AIX" in client.out


def test_profile_from_temp_absolute_path():
    """ When passing absolute path as profile file, it MUST be used
        conan install . -pr=/tmp/profiles/default
        /tmp/profiles/default MUST be consumed as target profile
    """
    client = TestClient()
    client.save({"profiles/default": "[settings]\nos=AIX",
                 "current/conanfile.txt": ""})
    profile_path = os.path.join(client.current_folder, "profiles", "default")
    recipe_path = os.path.join(client.current_folder, "current", "conanfile.txt")
    client.run('install "{}" -pr="{}"'.format(recipe_path, profile_path))
    assert "os=AIX" in client.out


def test_consumer_specific_settings():
    client = TestClient()
    dep = str(GenConanfile().with_settings("build_type").with_option("shared", [True, False])
              .with_default_option("shared", False))
    configure = """
    def configure(self):
        self.output.warning("I'm {} and my build type is {}".format(self.name,
                                                                 self.settings.build_type))
        self.output.warning("I'm {} and my shared is {}".format(self.name, self.options.shared))
    """
    dep += configure
    client.save({"conanfile.py": dep})
    client.run("create . --name=dep --version=1.0")
    client.run("create . --name=dep --version=1.0 -s build_type=Debug -o dep*:shared=True")

    consumer = str(GenConanfile().with_settings("build_type").with_requires("dep/1.0")
                   .with_option("shared", [True, False]).with_default_option("shared", False))
    consumer += configure
    client.save({"conanfile.py": consumer})

    # Regular install with release
    client.run("install . -s build_type=Release")
    assert "I'm dep and my build type is Release" in client.out
    assert "I'm None and my build type is Release" in client.out
    assert "I'm dep and my shared is False" in client.out
    assert "I'm None and my shared is False" in client.out

    # Now the dependency by name
    client.run("install . -s dep/*:build_type=Debug -o dep/*:shared=True")
    assert "I'm dep and my build type is Debug" in client.out
    assert "I'm None and my build type is Release" in client.out
    assert "I'm dep and my shared is True" in client.out
    assert "I'm None and my shared is False" in client.out

    # Now the consumer using &
    client.run("install . -s &:build_type=Debug -o shared=True")
    assert "I'm dep and my build type is Release" in client.out
    assert "I'm None and my build type is Debug" in client.out
    assert "I'm dep and my shared is False" in client.out
    assert "I'm None and my shared is True" in client.out

    # Now use a conanfile.txt
    client.save({"conanfile.txt": textwrap.dedent("""
            [requires]
            dep/1.0
    """)}, clean_first=True)

    # Regular install with release
    client.run("install . -s build_type=Release")
    assert "I'm dep and my build type is Release" in client.out

    # Now the dependency by name
    client.run("install . -s dep*:build_type=Debug -o dep*:shared=True")
    assert "I'm dep and my build type is Debug" in client.out
    assert "I'm dep and my shared is True" in client.out

    # Test that the generators take the setting
    if platform.system() != "Windows":  # Toolchain in windows is multiconfig
        # Now the consumer using &
        client.run("install . -s &:build_type=Debug -g CMakeToolchain")
        assert "I'm dep and my build type is Release" in client.out
        # Verify the cmake toolchain takes Debug
        assert "I'm dep and my shared is False" in client.out
        presets = json.loads(client.load("CMakePresets.json"))
        assert presets["configurePresets"][0]["cacheVariables"]['CMAKE_BUILD_TYPE'] == "Debug"


def test_create_and_priority_of_consumer_specific_setting():
    client = TestClient()
    conanfile = str(GenConanfile().with_settings("build_type").with_name("foo").with_version("1.0"))
    configure = """
    def configure(self):
        self.output.warning("I'm {} and my build type is {}".format(self.name,
                                                                 self.settings.build_type))
    """
    conanfile += configure
    client.save({"conanfile.py": conanfile})
    client.run("create . -s foo*:build_type=Debug")
    assert "I'm foo and my build type is Debug" in client.out

    client.run("create . -s foo*:build_type=Debug -s &:build_type=Release")
    assert "I'm foo and my build type is Release" in client.out

    # The order DOES matter
    client.run("create . -s &:build_type=Release -s foo*:build_type=Debug ")
    assert "I'm foo and my build type is Debug" in client.out

    # With test_package also works
    test = str(GenConanfile().with_test("pass").with_setting("build_type"))
    test += configure
    client.save({"test_package/conanfile.py": test})
    client.run("create . -s &:build_type=Debug -s build_type=Release")
    assert "I'm foo and my build type is Debug" in client.out
    # the test package recipe has debug too
    assert "I'm None and my build type is Debug" in client.out


def test_consumer_specific_settings_from_profile():
    client = TestClient()
    conanfile = str(GenConanfile().with_settings("build_type").with_name("hello"))
    configure = """
    def configure(self):
        self.output.warning("I'm {} and my build type is {}".format(self.name,
                                                                 self.settings.build_type))
    """
    conanfile += configure
    profile = textwrap.dedent("""
        include(default)
        [settings]
        &:build_type=Debug
    """)
    client.save({"conanfile.py": conanfile, "my_profile.txt": profile})
    client.run("install . --profile my_profile.txt")
    assert "I'm hello and my build type is Debug" in client.out


def test_consumer_invalid_profile_multiple_groups():
    """
    Issue related: https://github.com/conan-io/conan/issues/16448
    """
    client = TestClient()
    conanfile = GenConanfile(name="hello", version="1.0").with_settings("os", "arch",
                                                                        "build_type", "compiler")
    prof1 = textwrap.dedent("""\
    [settings]
    arch=x86_64
    os=Linux
    build_type=Release
    compiler=clang
    compiler.libcxx=libstdc++11
    compiler.version=18
    compiler.cppstd=20

    [conf]
    tools.build:compiler_executables={'c': '/usr/bin/clang-18', 'cpp': '/usr/bin/clang++-18'}

    [settings]
    # Empty and duplicated section

    [options]
    package/*:option=Whatever

    [conf]
    # Another one
    """)
    client.save({
        "conanfile.py": conanfile,
        "myprofs/myprofile": prof1
    })
    client.run("build . --profile:host myprofs/myprofile -g CMakeToolchain",
               assert_error=True)
    assert ("ERROR: Error reading 'myprofs/myprofile' profile: ConfigParser: "
            "Duplicated section: [settings]") in client.out
