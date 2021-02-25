import os
import textwrap
from collections import defaultdict
from importlib.util import spec_from_file_location, module_from_spec

import pytest

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


@pytest.fixture
def client():
    return TestClient()


@pytest.fixture
def pr1_content():
    return textwrap.dedent("""
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


@pytest.fixture
def pr2_content():
    return textwrap.dedent("""
        from conans import settings, options, env

        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "16"

        options.shared = False
        options.fPIC = True

        env.cpu_count = "12"
        """)


def test_settings_simple():
    settings = ProfileSettings()
    settings.value()
    assert {} == settings.value()


def test_settings():
    settings = ProfileSettings()
    settings.os = "Windows"
    settings.compiler = "Visual"
    settings.compiler.version = "16"
    settings.whatever.annd.ever = "14"
    assert settings.os.value() == "Windows"
    assert settings.compiler.value() == {"Visual": {"version": "16"}}
    assert settings.compiler.version.value() == "16"
    assert settings.whatever.annd.ever.value() == "14"
    assert settings.value() == {"os": "Windows",
                                "compiler": {"Visual": {"version": "16"}},
                                "whatever": {"annd": {"ever": "14"}}
                                }


def test_options():
    options = ProfileOptions()
    options.shared = True
    options.SHARED = False
    options.fpic = True
    options.fpic = False
    options["new"] = "other"
    assert options.shared is True
    assert options.SHARED is False
    assert options.fpic is False
    assert options.new == "other"
    assert options["new"] == "other"


def test_load_profile(client, pr1_content, pr2_content):
    client.save({"profile.py": pr2_content})
    profile_path = os.path.join(client.current_folder, "profile.py")
    profile = ProfileLoader.load_profile_python(profile_path)
    assert profile["settings"].value() == {"os": "Windows",
                                           "compiler": {"Visual Studio": {"version": "16"}}}
    assert profile["options"] == {"shared": False, "fPIC": True}
    assert profile["env"] == {"cpu_count": "12"}


def test_load_unrelated_profiles(client, pr1_content, pr2_content):
    client.save({"pr1.py": pr1_content, "pr2.py": pr2_content})
    pr1_path = os.path.join(client.current_folder, "pr1.py")
    with environment_append({"CXXFLAGS": "-fPIC"}):
        profile1 = ProfileLoader.load_profile_python(pr1_path)
    assert profile1["settings"].value() == {"os": "Linux", "build_type": "Release"}
    assert profile1["options"] == {"shared": True}
    assert profile1["env"] == {"env_var": "bar", "CXXFLAGS": "-fPIC -stdlib=libc++11"}

    pr2_path = os.path.join(client.current_folder, "pr2.py")
    profile2 = ProfileLoader.load_profile_python(pr2_path)
    assert profile2["settings"].value() == {"os": "Windows",
                                            "compiler": {"Visual Studio": {"version": "16"}}}
    assert profile2["options"] == {"shared": False, "fPIC": True}
    assert profile2["env"] == {"cpu_count": "12"}


def test_load_command_line_related_profiles(client, pr1_content, pr2_content):
    # Equivalent to conan install ... --profile pr1 --profile pr2
    client.save({"pr1.py": pr1_content, "pr2.py": pr2_content})
    pr1_path = os.path.join(client.current_folder, "pr1.py")
    with environment_append({"CXXFLAGS": "-fPIC"}):
        profile1 = ProfileLoader.load_profile_python(pr1_path)
    assert profile1["settings"].value() == {"os": "Linux", "build_type": "Release"}
    assert profile1["options"] == {"shared": True}
    assert profile1["env"] == {"env_var": "bar", "CXXFLAGS": "-fPIC -stdlib=libc++11"}

    pr2_path = os.path.join(client.current_folder, "pr2.py")
    with environment_append({"CXXFLAGS": "-fPIC"}):
        profile2 = ProfileLoader.load_profile_python(pr2_path, pr1_path)
    assert profile2["settings"].value() == {"os": "Windows",
                                            "compiler": {"Visual Studio": {"version": "16"}},
                                            "build_type": "Release"}
    assert profile2["options"] == {"shared": False, "fPIC": True}
    assert profile2["env"] == {"env_var": "bar", "CXXFLAGS": "-fPIC -stdlib=libc++11",
                               "cpu_count": "12"}
