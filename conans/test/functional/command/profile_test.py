import os
import unittest
import platform
import subprocess
import json

import pytest

from conans.client import tools
from conans.test.utils.profiles import create_profile
from conans.client.conf.detect import detect_defaults_settings
from conans.test.utils.tools import TestClient
from conans.util.files import load
from conans.util.runners import check_output_runner
from conans.paths import DEFAULT_PROFILE_NAME
from conans.test.utils.mocks import TestBufferConanOutput


class ProfileTest(unittest.TestCase):

    def test_reuse_output(self):
        client = TestClient()
        client.run("profile new myprofile --detect")
        client.run("profile update options.Pkg:myoption=123 myprofile")
        client.run("profile update env.Pkg2:myenv=123 myprofile")
        client.run("profile update conf.tools.ninja:jobs=10 myprofile")
        client.run("profile show myprofile")
        self.assertIn("Pkg:myoption=123", client.out)
        self.assertIn("Pkg2:myenv=123", client.out)
        self.assertIn("tools.ninja:jobs=10", client.out)
        profile = str(client.out).splitlines()[2:]
        client.save({"conanfile.txt": "",
                     "mylocalprofile": "\n".join(profile)})
        client.run("install . -pr=mylocalprofile")
        self.assertIn("conanfile.txt: Generated conaninfo.txt", client.out)

    def test_empty(self):
        client = TestClient(cache_autopopulate=False)
        client.run("profile list")
        self.assertIn("No profiles defined", client.out)

    def test_list(self):
        client = TestClient()
        profiles = ["default", "profile1", "profile2", "profile3",
                    "nested" + os.path.sep + "profile4",
                    "nested" + os.path.sep + "two" + os.path.sep + "profile5",
                    "nested" + os.path.sep + "profile6"]
        if platform.system() != "Windows":
            profiles.append("symlink_me" + os.path.sep + "profile7")
        for profile in profiles:
            create_profile(client.cache.profiles_path, profile)

        if platform.system() != "Windows":
            os.symlink(os.path.join(client.cache.profiles_path, 'symlink_me'),
                       os.path.join(client.cache.profiles_path, 'link'))
            # profile7 will be shown twice because it is symlinked.
            profiles.append("link" + os.path.sep + "profile7")

        # Make sure local folder doesn't interact with profiles
        os.mkdir(os.path.join(client.current_folder, "profile3"))
        client.run("profile list")
        profiles.sort()
        self.assertEqual(profiles, list(str(client.out).splitlines()))

        # Test profile list json file
        client.run("profile list --json profile_list.json")
        json_path = os.path.join(client.current_folder, "profile_list.json")
        self.assertTrue(os.path.exists(json_path))
        json_content = load(json_path)
        json_obj = json.loads(json_content)
        self.assertEqual(list, type(json_obj))
        self.assertEqual(profiles, json_obj)

    def test_show(self):
        client = TestClient()
        create_profile(client.cache.profiles_path, "profile1", settings={"os": "Windows"},
                       options=[("MyOption", "32")])
        create_profile(client.cache.profiles_path, "profile3",
                       env=[("package:VAR", "value"), ("CXX", "/path/tomy/g++_build"),
                            ("CC", "/path/tomy/gcc_build")],
                       conf=["tools.ninja:jobs=10", "tools.gnu.make:jobs=20"])
        client.run("profile show profile1")
        self.assertIn("[settings]\nos=Windows", client.out)
        self.assertIn("MyOption=32", client.out)
        client.run("profile show profile3")
        self.assertIn("CC=/path/tomy/gcc_build", client.out)
        self.assertIn("CXX=/path/tomy/g++_build", client.out)
        self.assertIn("package:VAR=value", client.out)
        self.assertIn("tools.ninja:jobs=10", client.out)
        self.assertIn("tools.gnu.make:jobs=20", client.out)

    def test_profile_update_and_get(self):
        client = TestClient()
        client.run("profile new ./MyProfile --detect")
        if "WARNING: GCC OLD ABI COMPATIBILITY" in client.out:
            self.assertIn("Or edit '{}/MyProfile' and "
                          "set compiler.libcxx=libstdc++11".format(client.current_folder),
                          client.out)

        pr_path = os.path.join(client.current_folder, "MyProfile")

        client.run("profile update settings.os=FakeOS ./MyProfile")
        self.assertIn("\nos=FakeOS", load(pr_path))
        self.assertNotIn("\nos=Linux", load(pr_path))

        client.run("profile get settings.os ./MyProfile")
        self.assertEqual(client.out, "FakeOS\n")

        client.run("profile update settings.compiler.version=88 ./MyProfile")
        self.assertIn("compiler.version=88", load(pr_path))

        client.run("profile get settings.compiler.version ./MyProfile")
        self.assertEqual(client.out, "88\n")

        client.run("profile update options.MyOption=23 ./MyProfile")
        self.assertIn("[options]\nMyOption=23", load(pr_path))

        client.run("profile get options.MyOption ./MyProfile")
        self.assertEqual(client.out, "23\n")

        client.run("profile update options.Package:MyOption=23 ./MyProfile")
        self.assertIn("Package:MyOption=23", load(pr_path))

        client.run("profile get options.Package:MyOption ./MyProfile")
        self.assertEqual(client.out, "23\n")

        client.run("profile update options.Package:OtherOption=23 ./MyProfile")
        self.assertIn("Package:OtherOption=23", load(pr_path))

        client.run("profile get options.Package:OtherOption ./MyProfile")
        self.assertEqual(client.out, "23\n")

        client.run("profile update env.OneMyEnv=MYVALUe ./MyProfile")
        self.assertIn("[env]\nOneMyEnv=MYVALUe", load(pr_path))

        client.run("profile get env.OneMyEnv ./MyProfile")
        self.assertEqual(client.out, "MYVALUe\n")

        client.run("profile update conf.tools.ninja:jobs=10 ./MyProfile")
        self.assertIn("[conf]\ntools.ninja:jobs=10", load(pr_path))

        client.run("profile get conf.tools.ninja:jobs ./MyProfile")
        self.assertEqual(client.out, "10\n")

        client.run("profile update conf.tools.gnu.make:jobs=20 ./MyProfile")
        self.assertIn("tools.gnu.make:jobs=20", load(pr_path))

        client.run("profile get conf.tools.gnu.make:jobs ./MyProfile")
        self.assertEqual(client.out, "20\n")

        # Now try the remove

        client.run("profile remove settings.os ./MyProfile")
        client.run("profile remove settings.os_build ./MyProfile")
        self.assertNotIn("os=", load(pr_path))

        client.run("profile remove settings.compiler.version ./MyProfile")
        self.assertNotIn("compiler.version", load(pr_path))

        client.run("profile remove options.MyOption ./MyProfile")
        self.assertNotIn("[options]\nMyOption", load(pr_path))

        client.run("profile remove options.Package:MyOption ./MyProfile")
        self.assertNotIn("Package:MyOption", load(pr_path))
        self.assertIn("Package:OtherOption", load(pr_path))

        client.run("profile remove conf.tools.gnu.make:jobs ./MyProfile")
        self.assertNotIn("tools.gnu.make:jobs", load(pr_path))
        self.assertIn("tools.ninja:jobs", load(pr_path))

        client.run("profile remove env.OneMyEnv ./MyProfile")
        self.assertNotIn("OneMyEnv", load(pr_path))

        # Remove a non existent key
        client.run("profile remove settings.os ./MyProfile", assert_error=True)
        self.assertIn("Profile key 'settings.os' doesn't exist", client.out)

        client.run("profile remove options.foo ./MyProfile", assert_error=True)
        self.assertIn("Profile key 'options.foo' doesn't exist", client.out)

        client.run("profile remove env.foo ./MyProfile", assert_error=True)
        self.assertIn("Profile key 'env.foo' doesn't exist", client.out)

        client.run("profile remove conf.MyConf ./MyProfile", assert_error=True)
        self.assertIn("Profile key 'conf.MyConf' doesn't exist", client.out)

    def test_profile_update_env(self):
        client = TestClient()
        client.run("profile new ./MyProfile")
        pr_path = os.path.join(client.current_folder, "MyProfile")

        client.run("profile update env.foo=bar ./MyProfile")
        self.assertEqual(["[env]", "foo=bar"], load(pr_path).splitlines()[-2:])
        client.run("profile update env.foo=BAZ ./MyProfile")
        self.assertEqual(["[env]", "foo=BAZ"], load(pr_path).splitlines()[-2:])
        client.run("profile update env.MyPkg:foo=FOO ./MyProfile")
        self.assertEqual(["[env]", "foo=BAZ", "MyPkg:foo=FOO"], load(pr_path).splitlines()[-3:])
        client.run("profile update env.MyPkg:foo=FOO,BAZ,BAR ./MyProfile")
        self.assertEqual(["[env]", "foo=BAZ", "MyPkg:foo=FOO,BAZ,BAR"],
                         load(pr_path).splitlines()[-3:])

    def test_profile_new(self):
        client = TestClient()
        client.run("profile new ./MyProfile")
        pr_path = os.path.join(client.current_folder, "MyProfile")
        self.assertTrue(os.path.exists(pr_path))
        self.assertEqual(load(pr_path), """[settings]
[options]
[build_requires]
[env]
""")

        client.run("profile new ./MyProfile2 --detect")
        pr_path = os.path.join(client.current_folder, "MyProfile2")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "MyProfile2")))
        self.assertIn("os=", load(pr_path))

        client.run("profile new ./MyProfile2 --detect", assert_error=True)
        self.assertIn("Profile already exists", client.out)

        client.run("profile new MyProfile3")
        pr_path = os.path.join(client.cache.profiles_path, "MyProfile3")
        self.assertTrue(os.path.exists(pr_path))
        self.assertNotIn("os=", load(pr_path))

    def test_profile_force_new(self):
        client = TestClient()

        empty_profile = """[settings]
[options]
[build_requires]
[env]
"""
        client.run("profile new ./MyProfile")
        pr_path = os.path.join(client.current_folder, "MyProfile")
        self.assertTrue(os.path.exists(pr_path))
        self.assertEqual(load(pr_path), empty_profile)

        client.run("profile new ./MyProfile --detect", assert_error=True)
        self.assertIn("Profile already exists", client.out)

        client.run("profile new ./MyProfile --detect --force", assert_error=False)
        self.assertNotEqual(load(pr_path), empty_profile)

        detected_profile = load(pr_path)

        client.run("profile update settings.os=FakeOS ./MyProfile")
        self.assertIn("\nos=FakeOS", load(pr_path))

        client.run("profile update env.MyEnv=MYVALUe ./MyProfile")
        self.assertIn("[env]\nMyEnv=MYVALUe", load(pr_path))

        client.run("profile new ./MyProfile --detect --force", assert_error=False)
        self.assertNotIn("\nos=FakeOS", load(pr_path))
        self.assertNotIn("[env]\nMyEnv=MYVALUe", load(pr_path))
        self.assertEqual(load(pr_path), detected_profile)

    def test_missing_subarguments(self):
        client = TestClient()
        client.run("profile", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", client.out)


class DetectCompilersTest(unittest.TestCase):
    def test_detect_default_compilers(self):
        platform_default_compilers = {
            "Linux": "gcc",
            "Darwin": "apple-clang",
            "Windows": "Visual Studio"
        }
        output = TestBufferConanOutput()
        result = detect_defaults_settings(output, profile_path=DEFAULT_PROFILE_NAME)
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        platform_compiler = platform_default_compilers.get(platform.system(), None)
        if platform_compiler is not None:
            self.assertEqual(result.get("compiler", None), platform_compiler)

    @pytest.mark.tool_gcc
    @pytest.mark.skipif(platform.system() != "Darwin", reason="only OSX test")
    def test_detect_default_in_mac_os_using_gcc_as_default(self):
        """
        Test if gcc in Mac OS X is using apple-clang as frontend
        """
        # See: https://github.com/conan-io/conan/issues/2231
        output = check_output_runner(["gcc", "--version"], stderr=subprocess.STDOUT)

        if "clang" not in output:
            # Not test scenario gcc should display clang in output
            # see: https://stackoverflow.com/questions/19535422/os-x-10-9-gcc-links-to-clang
            raise Exception("Apple gcc doesn't point to clang with gcc frontend anymore!")

        output = TestBufferConanOutput()
        with tools.environment_append({"CC": "gcc"}):
            result = detect_defaults_settings(output, profile_path=DEFAULT_PROFILE_NAME)
        # result is a list of tuples (name, value) so converting it to dict
        result = dict(result)
        # No compiler should be detected
        self.assertIsNone(result.get("compiler", None))
        self.assertIn("gcc detected as a frontend using apple-clang", output)
        self.assertIsNotNone(output.error)
