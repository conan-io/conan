import os
import textwrap
import unittest
from collections import defaultdict

from importlib.util import spec_from_file_location, module_from_spec

from conans.client.tools import environment_append
from conans.test.utils.tools import TestClient
from conans import ProfileSettings, ProfileOptions


class ProfileLoader(object):

    @staticmethod
    def _init_profile():
        import conans
        conans.settings = ProfileSettings()
        conans.options = ProfileOptions()
        conans.env = ProfileOptions()

    @staticmethod
    def _load_module_from_file(filename):
        name = os.path.splitext(os.path.basename(filename))[0]
        spec = spec_from_file_location(name, filename)
        config = module_from_spec(spec)
        spec.loader.exec_module(config)
        return config

    @staticmethod
    def _load_profile(profile_path):
        profile = {}
        profile_content = ProfileLoader._load_module_from_file(profile_path)
        for key, value in profile_content.__dict__.items():
            if not key.startswith("__"):
                profile[key] = value
        return profile.copy()

    @staticmethod
    def load_profile_python(profile_path, parent_profile_path=None):
        # TODO: implement include() of other profiles? variable substitution?
        if parent_profile_path:
            ProfileLoader._load_profile(parent_profile_path)
        profile = ProfileLoader._load_profile(profile_path)
        ProfileLoader._init_profile()
        return profile.copy()


class PythonProfilesTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.pr1_content = textwrap.dedent("""
            import os
            from conans import settings, options, env

            settings.os = "Linux"
            settings.build_type = "Release"

            options.shared = True

            env.env_var = "bar"
            cxxflags = os.environ.get('CXXFLAGS', "")
            if cxxflags:
                env.CXXFLAGS = cxxflags + " -stdlib=libc++11"
            """)
        self.pr2_content = textwrap.dedent("""
            from conans import settings, options, env

            settings.os = "Windows"
            settings.compiler = "Visual Studio"
            settings.compiler.version = "16"

            options.shared = False
            options.fPIC = True

            env.cpu_count = "12"
            """)

    def test_settings_simple(self):
        settings = ProfileSettings()
        settings.value()
        self.assertDictEqual({}, settings.value())

    def test_settings(self):
        settings = ProfileSettings()
        settings.os = "Windows"
        settings.compiler = "Visual"
        settings.compiler.version = "16"
        settings.whatever.annd.ever = "14"
        self.assertIn("Windows", settings.os.value())
        self.assertIn("Visual", settings.compiler.value())
        self.assertIn("16", settings.compiler.version.value())
        self.assertIn("14", settings.whatever.annd.ever.value())
        self.assertDictEqual({"os": "Windows",
                              "compiler": {"Visual": {"version": "16"}},
                              "whatever": {"annd": {"ever": "14"}}
                              }, settings.value())

    def test_options(self):
        options = ProfileOptions()
        options.shared = True
        options.SHARED = False
        options.fpic = True
        options.fpic = False
        options["new"] = "other"
        self.assertTrue(options.shared)
        self.assertFalse(options.SHARED)
        self.assertFalse(options.fpic)
        self.assertIn("other", options.new)
        self.assertIn("other", options["new"])

    def test_load_profile(self):
        self.client.save({"profile.py": self.pr2_content})
        profile_path = os.path.join(self.client.current_folder, "profile.py")
        profile = ProfileLoader.load_profile_python(profile_path)
        self.assertDictEqual({"os": "Windows", "compiler": {"Visual Studio": {"version": "16"}}},
                             profile["settings"].value())
        self.assertDictEqual({"shared": False, "fPIC": True}, profile["options"])
        self.assertDictEqual({"cpu_count": "12"}, profile["env"])

    def test_load_unrelated_profiles(self):
        self.client.save({"pr1.py": self.pr1_content, "pr2.py": self.pr2_content})
        pr1_path = os.path.join(self.client.current_folder, "pr1.py")
        with environment_append({"CXXFLAGS": "-fPIC"}):
            profile1 = ProfileLoader.load_profile_python(pr1_path)
        self.assertDictEqual({"os": "Linux", "build_type": "Release"},
                             profile1["settings"].value())
        self.assertDictEqual({"shared": True}, profile1["options"])
        self.assertDictEqual({"env_var": "bar", "CXXFLAGS": "-fPIC -stdlib=libc++11"},
                             profile1["env"])

        pr2_path = os.path.join(self.client.current_folder, "pr2.py")
        profile2 = ProfileLoader.load_profile_python(pr2_path)
        self.assertDictEqual({"os": "Windows",
                              "compiler": {"Visual Studio": {"version": "16"}}},
                             profile2["settings"].value())
        self.assertDictEqual({"shared": False, "fPIC": True}, profile2["options"])
        self.assertDictEqual({"cpu_count": "12"}, profile2["env"])

    def test_load_command_line_related_profiles(self):
        # Equivalent to conan install ... --profile pr1 --profile pr2
        self.client.save({"pr1.py": self.pr1_content, "pr2.py": self.pr2_content})
        pr1_path = os.path.join(self.client.current_folder, "pr1.py")
        with environment_append({"CXXFLAGS": "-fPIC"}):
            profile1 = ProfileLoader.load_profile_python(pr1_path)
        self.assertDictEqual({"os": "Linux", "build_type": "Release"},
                             profile1["settings"].value())
        self.assertDictEqual(profile1["options"], {"shared": True})
        self.assertDictEqual(profile1["env"], {"env_var": "bar",
                                               "CXXFLAGS": "-fPIC -stdlib=libc++11"})

        pr2_path = os.path.join(self.client.current_folder, "pr2.py")
        with environment_append({"CXXFLAGS": "-fPIC"}):
            profile2 = ProfileLoader.load_profile_python(pr2_path, pr1_path)
        self.assertDictEqual({"os": "Windows",
                              "compiler": {"Visual Studio": {"version": "16"}},
                              "build_type": "Release"},
                             profile2["settings"].value())
        self.assertDictEqual({"shared": False, "fPIC": True}, profile2["options"])
        self.assertDictEqual({"env_var": "bar",
                              "CXXFLAGS": "-fPIC -stdlib=libc++11",
                              "cpu_count": "12"},
                             profile2["env"])
