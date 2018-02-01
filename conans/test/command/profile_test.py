import unittest

import os

from conans.test.utils.tools import TestClient
from conans.test.utils.profiles import create_profile
from conans.util.files import load


class ProfileTest(unittest.TestCase):

    def reuse_output_test(self):
        client = TestClient()
        client.run("profile new myprofile --detect")
        client.run("profile update options.Pkg:myoption=123 myprofile")
        client.run("profile update env.Pkg2:myenv=123 myprofile")
        client.run("profile show myprofile")
        self.assertIn("Pkg:myoption=123", client.out)
        self.assertIn("Pkg2:myenv=123", client.out)
        profile = str(client.out).splitlines()[2:]
        client.save({"conanfile.txt": "",
                     "mylocalprofile": "\n".join(profile)})
        client.run("install . -pr=mylocalprofile")
        self.assertIn("PROJECT: Generated conaninfo.txt", client.out)

    def empty_test(self):
        client = TestClient()
        client.run("profile list")
        self.assertIn("No profiles defined", client.user_io.out)

    def list_test(self):
        client = TestClient()
        create_profile(client.client_cache.profiles_path, "profile3")
        create_profile(client.client_cache.profiles_path, "profile1")
        create_profile(client.client_cache.profiles_path, "profile2")
        # Make sure local folder doesn't interact with profiles
        os.mkdir(os.path.join(client.current_folder, "profile3"))
        client.run("profile list")
        self.assertEqual(list(["profile1", "profile2", "profile3"]),
                         list(str(client.user_io.out).splitlines()))

    def show_test(self):
        client = TestClient()
        create_profile(client.client_cache.profiles_path, "profile1", settings={"os": "Windows"},
                       options=[("MyOption", "32")])
        create_profile(client.client_cache.profiles_path, "profile3",
                       env=[("package:VAR", "value"), ("CXX", "/path/tomy/g++_build"),
                            ("CC", "/path/tomy/gcc_build")])
        client.run("profile show profile1")
        self.assertIn("[settings]\nos=Windows", client.user_io.out)
        self.assertIn("MyOption=32", client.user_io.out)
        client.run("profile show profile3")
        self.assertIn("CC=/path/tomy/gcc_build", client.user_io.out)
        self.assertIn("CXX=/path/tomy/g++_build", client.user_io.out)
        self.assertIn("package:VAR=value", client.user_io.out)

    def profile_update_and_get_test(self):
        client = TestClient()
        client.run("profile new ./MyProfile --detect")
        pr_path = os.path.join(client.current_folder, "MyProfile")

        client.run("profile update settings.os=FakeOS ./MyProfile")
        self.assertIn("\nos=FakeOS", load(pr_path))
        self.assertNotIn("\nos=Linux", load(pr_path))

        client.run("profile get settings.os ./MyProfile")
        self.assertEquals(client.out, "FakeOS\n")

        client.run("profile update settings.compiler.version=88 ./MyProfile")
        self.assertIn("compiler.version=88", load(pr_path))

        client.run("profile get settings.compiler.version ./MyProfile")
        self.assertEquals(client.out, "88\n")

        client.run("profile update options.MyOption=23 ./MyProfile")
        self.assertIn("[options]\nMyOption=23", load(pr_path))

        client.run("profile get options.MyOption ./MyProfile")
        self.assertEquals(client.out, "23\n")

        client.run("profile update options.Package:MyOption=23 ./MyProfile")
        self.assertIn("Package:MyOption=23", load(pr_path))

        client.run("profile get options.Package:MyOption ./MyProfile")
        self.assertEquals(client.out, "23\n")

        client.run("profile update options.Package:OtherOption=23 ./MyProfile")
        self.assertIn("Package:OtherOption=23", load(pr_path))

        client.run("profile get options.Package:OtherOption ./MyProfile")
        self.assertEquals(client.out, "23\n")

        client.run("profile update env.OneMyEnv=MYVALUe ./MyProfile")
        self.assertIn("[env]\nOneMyEnv=MYVALUe", load(pr_path))

        client.run("profile get env.OneMyEnv ./MyProfile")
        self.assertEquals(client.out, "MYVALUe\n")

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

        client.run("profile remove env.OneMyEnv ./MyProfile")
        self.assertNotIn("OneMyEnv", load(pr_path))

        # Remove a non existent key
        client.run("profile remove settings.os ./MyProfile", ignore_error=True)
        self.assertIn("Profile key 'settings.os' doesn't exist", client.user_io.out)

        client.run("profile remove options.foo ./MyProfile", ignore_error=True)
        self.assertIn("Profile key 'options.foo' doesn't exist", client.user_io.out)

        client.run("profile remove env.foo ./MyProfile", ignore_error=True)
        self.assertIn("Profile key 'env.foo' doesn't exist", client.user_io.out)

    def profile_new_test(self):
        client = TestClient()
        client.run("profile new ./MyProfile")
        pr_path = os.path.join(client.current_folder, "MyProfile")
        self.assertTrue(os.path.exists(pr_path))
        self.assertEquals(load(pr_path), """[settings]
[options]
[build_requires]
[env]
""")

        client.run("profile new ./MyProfile2 --detect")
        pr_path = os.path.join(client.current_folder, "MyProfile2")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "MyProfile2")))
        self.assertIn("os=", load(pr_path))

        client.run("profile new ./MyProfile2 --detect", ignore_error=True)
        self.assertIn("Profile already exists", client.user_io.out)

        client.run("profile new MyProfile3")
        pr_path = os.path.join(client.client_cache.profiles_path, "MyProfile3")
        self.assertTrue(os.path.exists(pr_path))
        self.assertNotIn("os=", load(pr_path))
