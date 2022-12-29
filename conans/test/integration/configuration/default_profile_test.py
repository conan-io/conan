import os
import textwrap
import unittest

from conans.client import tools
from conans.client.cache.cache import PROFILES_FOLDER
from conans.paths import CONANFILE
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient
from conans.util.files import save


class DefaultProfileTest(unittest.TestCase):

    def test_conanfile_txt_incomplete_profile(self):
        conanfile = '''from conans import ConanFile
class MyConanfile(ConanFile):
    pass
'''

        client = TestClient()
        save(client.cache.default_profile_path, "[env]\nValue1=A")

        client.save({CONANFILE: conanfile})
        client.run("create . Pkg/0.1@lasote/stable")
        self.assertIn("Pkg/0.1@lasote/stable: Package '%s' created" % NO_SETTINGS_PACKAGE_ID,
                      client.out)

        client.save({"conanfile.txt": "[requires]\nPkg/0.1@lasote/stable"}, clean_first=True)
        client.run('install .')
        self.assertIn("Pkg/0.1@lasote/stable: Already installed!", client.out)

    def test_change_default_profile(self):
        br = '''
import os
from conans import ConanFile

class MyConanfile(ConanFile):
    name = "mylib"
    version = "0.1"

    def build(self):
        assert(os.environ.get("Value1") == "A")

'''
        tmp = temp_folder()
        default_profile_path = os.path.join(tmp, "myprofile")
        save(default_profile_path, "[env]\nValue1=A")
        client = TestClient()
        client.run("config set general.default_profile='%s'" % default_profile_path)
        client.save({CONANFILE: br})
        client.run("export . lasote/stable")
        client.run('install mylib/0.1@lasote/stable --build')

        # Now use a name, in the default profile folder
        os.unlink(default_profile_path)
        save(os.path.join(client.cache.profiles_path, "other"), "[env]\nValue1=A")
        client.run("config set general.default_profile=other")
        client.save({CONANFILE: br})
        client.run("export . lasote/stable")
        client.run('install mylib/0.1@lasote/stable --build')

    def test_profile_applied_ok(self):
        br = '''
import os
from conans import ConanFile

class BuildRequireConanfile(ConanFile):
    name = "br"
    version = "1.0"
    settings = "os", "compiler", "arch"

    def package_info(self):
        self.env_info.MyVAR="from_build_require"
'''

        client = TestClient()

        default_profile = """
[settings]
os=Windows
compiler=Visual Studio
compiler.version=14
compiler.runtime=MD
arch=x86

[options]
mypackage:option1=2

[build_requires]
br/1.0@lasote/stable
"""
        save(client.cache.default_profile_path, default_profile)

        client.save({CONANFILE: br})
        client.run("export . lasote/stable")

        cf = '''
import os
from conans import ConanFile

class MyConanfile(ConanFile):
    name = "mypackage"
    version = "0.1"
    settings = "os", "compiler", "arch"
    options = {"option1": ["1", "2"]}
    default_options = "option1=1"

    def configure(self):
        assert(self.settings.os=="Windows")
        assert(self.settings.compiler=="Visual Studio")
        assert(self.settings.compiler.version=="14")
        assert(self.settings.compiler.runtime=="MD")
        assert(self.settings.arch=="x86")
        assert(self.options.option1=="2")

    def build(self):
        # This has changed, the value from profile higher priority than build require
        assert(os.environ["MyVAR"]=="%s")

        '''

        # First apply just the default profile, we should get the env MYVAR="from_build_require"
        client.save({CONANFILE: cf % "from_build_require"}, clean_first=True)
        client.run("export . lasote/stable")
        client.run('install mypackage/0.1@lasote/stable --build missing')

        # Then declare in the default profile the var, it should be prioritized from the br
        default_profile_2 = default_profile + "\n[env]\nMyVAR=23"
        save(client.cache.default_profile_path, default_profile_2)
        client.save({CONANFILE: cf % "23"}, clean_first=True)
        client.run("export . lasote/stable")
        client.run('install mypackage/0.1@lasote/stable --build missing')

    def test_env_default_profile(self):
        conanfile = '''
import os
from conans import ConanFile

class MyConanfile(ConanFile):

    def build(self):
        self.output.info(">>> env_variable={}".format(os.environ.get('env_variable')))
'''

        client = TestClient()
        client.save({CONANFILE: conanfile})

        # Test with the 'default' profile
        env_variable = "env_variable=profile_default"
        save(client.cache.default_profile_path, "[env]\n" + env_variable)
        client.run("create . name/version@user/channel")
        self.assertIn(">>> " + env_variable, client.out)

        # Test with a profile set using and environment variable
        tmp = temp_folder()
        env_variable = "env_variable=profile_environment"
        default_profile_path = os.path.join(tmp, 'env_profile')
        save(default_profile_path, "[env]\n" + env_variable)
        with tools.environment_append({'CONAN_DEFAULT_PROFILE_PATH': default_profile_path}):
            client.run("create . name/version@user/channel")
            self.assertIn(">>> " + env_variable, client.out)

        # Use relative path defined in environment variable
        env_variable = "env_variable=relative_profile"
        rel_path = os.path.join('..', 'env_rel_profile')
        self.assertFalse(os.path.isabs(rel_path))
        default_profile_path = os.path.join(client.cache_folder,
                                            PROFILES_FOLDER, rel_path)
        save(default_profile_path, "[env]\n" + env_variable)
        with tools.environment_append({'CONAN_DEFAULT_PROFILE_PATH': rel_path}):
            client.run("create . name/version@user/channel")
            self.assertIn(">>> " + env_variable, client.out)

        # Use non existing path
        profile_path = os.path.join(tmp, "this", "is", "a", "path")
        self.assertTrue(os.path.isabs(profile_path))
        with tools.environment_append({'CONAN_DEFAULT_PROFILE_PATH': profile_path}):
            client.run("create . name/version@user/channel", assert_error=True)
            self.assertIn("Environment variable 'CONAN_DEFAULT_PROFILE_PATH' must point to "
                          "an existing profile file.", client.out)


def test_conf_default_two_profiles():
    client = TestClient()
    save(os.path.join(client.cache.profiles_path, "mydefault"), "[settings]\nos=FreeBSD")
    save(os.path.join(client.cache.profiles_path, "mydefault_build"), "[settings]\nos=Android")
    global_conf = textwrap.dedent("""
        core:default_profile=mydefault
        core:default_build_profile=mydefault_build
        """)
    save(client.cache.new_config_path, global_conf)
    client.save({"conanfile.txt": ""})
    client.run("install .")
    assert "Configuration (profile_host):" in client.out
    assert "os=FreeBSD" in client.out
    assert "Configuration (profile_build):" in client.out
    assert "os=Android" in client.out

