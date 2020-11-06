import os
import textwrap
import unittest

from importlib.util import spec_from_file_location, module_from_spec

from conans.client.tools import environment_append
from conans.test.utils.tools import TestClient


class Profile(dict):

    def __init__(self):
        self["settings"] = {}
        self["options"] = {}
        self["env"] = {}

    @property
    def settings(self):
        return self["settings"]

    def update(self, profile):
        for k, v in profile.items():
            if k in ["settings", "options", "env"]:
                self[k].update(v)
            else:
                self[k] = v


def _load_module_from_file(filename, parent_profile):
    name = os.path.splitext(os.path.basename(filename))[0]
    spec = spec_from_file_location(name, filename)
    config = module_from_spec(spec)
    for key, value in parent_profile.items():
        setattr(config, key, value)
    spec.loader.exec_module(config)
    return config


def _load_profile_python(profile_path, parent_profile=None):
    # TODO: implement include() of other profiles? variable substitution?
    parent_profile = parent_profile or Profile()
    profile_content = _load_module_from_file(profile_path, parent_profile)
    profile = Profile()
    for key, value in profile_content.__dict__.items():
        if not key.startswith("__"):
            profile[key] = value
    parent_profile.update(profile)
    return parent_profile


class PythonProfilesTest(unittest.TestCase):

    def test_python_profile_create(self):
        client = TestClient()
        pr1_content = textwrap.dedent("""
            import os

            settings = {
                 "os": "Windows",
                 "compiler": "Visual Studio",
                 "compiler.version": "16",
                }
            options = {"shared": True}
            env = {"pkg:env_var": "bar"}
            cxxflags = os.environ.get('CXXFLAGS', "")
            if cxxflags:
                env['CXXFLAGS'] = cxxflags + " -stdlib=libc++11"
        """)
        pr2_content = textwrap.dedent("""
            from conans import tools

            settings = {"os": "Linux", "build_type": "Release"}
            env_values = {"cpu_count": str(tools.cpu_count())}
            if env:
                env.update(env_values)
            else:
                env = env_values
        """)
        client.save({"pr1.py": pr1_content, "pr2.py": pr2_content})
        pr1_path = os.path.join(client.current_folder, "pr1.py")
        with environment_append({"CXXFLAGS": "-fPIC"}):
            profile1 = _load_profile_python(pr1_path)
        self.assertDictEqual(profile1["settings"], {"os": "Windows", "compiler": "Visual Studio",
                                                 "compiler.version": "16"})
        self.assertDictEqual(profile1["options"], {"shared": True})
        self.assertDictEqual(profile1["env"], {"pkg:env_var": "bar",
                                            "CXXFLAGS": "-fPIC -stdlib=libc++11"})

        pr2_path = os.path.join(client.current_folder, "pr2.py")
        profile2 = _load_profile_python(pr2_path, profile1)
        self.assertDictEqual(profile2["settings"], {"os": "Linux",
                                                    "compiler": "Visual Studio",
                                                    "compiler.version": "16",
                                                    "build_type": "Release"})
        self.assertDictEqual(profile2["options"], {"shared": True})
        self.assertDictEqual(profile2["env"], {"pkg:env_var": "bar",
                                               "CXXFLAGS": "-fPIC -stdlib=libc++11",
                                               "cpu_count": "8"})
