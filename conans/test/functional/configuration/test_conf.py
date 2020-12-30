import textwrap

import pytest
from mock import patch

from conans.errors import ConanException
from conans.util.files import save
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):
            def generate(self):
                for k, conf in self.conf.items():
                    for name, value in conf.items():
                        self.output.info("{}${}${}".format(k, name, value))
        """)
    client.save({"conanfile.py": conanfile})
    return client


def test_basic_composition(client):
    profile1 = textwrap.dedent("""\
        [conf]
        tools.microsoft.MSBuild:verbosity=Quiet
        tools.microsoft.MSBuild:performance=Slow
        tools.cmake.CMake:verbosity=Extra
        """)
    profile2 = textwrap.dedent("""\
        [conf]
        tools.microsoft.MSBuild:verbosity=Minimal
        tools.microsoft.MSBuild:robustness=High
        tools.meson.Meson:verbosity=Super
        """)
    client.save({"profile1": profile1,
                 "profile2": profile2})
    client.run("install . -pr=profile1")
    assert "tools.microsoft.MSBuild$verbosity$Quiet" in client.out
    assert "tools.microsoft.MSBuild$performance$Slow" in client.out
    assert "tools.cmake.CMake$verbosity$Extra" in client.out

    client.run("install . -pr=profile1 -pr=profile2")
    assert "tools.microsoft.MSBuild$verbosity$Minimal" in client.out
    assert "tools.microsoft.MSBuild$performance$Slow" in client.out
    assert "tools.microsoft.MSBuild$robustness$High" in client.out
    assert "tools.cmake.CMake$verbosity$Extra" in client.out
    assert "tools.meson.Meson$verbosity$Super" in client.out

    client.run("install . -pr=profile2 -pr=profile1")
    assert "tools.microsoft.MSBuild$verbosity$Quiet" in client.out
    assert "tools.microsoft.MSBuild$performance$Slow" in client.out
    assert "tools.microsoft.MSBuild$robustness$High" in client.out
    assert "tools.cmake.CMake$verbosity$Extra" in client.out
    assert "tools.meson.Meson$verbosity$Super" in client.out


def test_basic_inclusion(client):
    profile1 = textwrap.dedent("""\
        [conf]
        tools.microsoft.MSBuild:verbosity=Quiet
        tools.microsoft.MSBuild:performance=Slow
        tools.cmake.CMake:verbosity=Extra
        """)
    profile2 = textwrap.dedent("""\
        include(profile1)
        [conf]
        tools.microsoft.MSBuild:verbosity=Minimal
        tools.microsoft.MSBuild:robustness=High
        tools.meson.Meson:verbosity=Super
        """)
    client.save({"profile1": profile1,
                 "profile2": profile2})

    client.run("install . -pr=profile2")
    assert "tools.microsoft.MSBuild$verbosity$Minimal" in client.out
    assert "tools.microsoft.MSBuild$performance$Slow" in client.out
    assert "tools.microsoft.MSBuild$robustness$High" in client.out
    assert "tools.cmake.CMake$verbosity$Extra" in client.out
    assert "tools.meson.Meson$verbosity$Super" in client.out


def test_composition_conan_conf(client):
    conf = textwrap.dedent("""\
        tools.microsoft.MSBuild:verbosity=Quiet
        tools.microsoft.MSBuild:performance=Slow
        tools.cmake.CMake:verbosity=Extra
        """)
    save(client.cache.new_config_path, conf)
    profile = textwrap.dedent("""\
        [conf]
        tools.microsoft.MSBuild:verbosity=Minimal
        tools.microsoft.MSBuild:robustness=High
        tools.meson.Meson:verbosity=Super
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile")
    assert "tools.microsoft.MSBuild$verbosity$Minimal" in client.out
    assert "tools.microsoft.MSBuild$performance$Slow" in client.out
    assert "tools.microsoft.MSBuild$robustness$High" in client.out
    assert "tools.cmake.CMake$verbosity$Extra" in client.out
    assert "tools.meson.Meson$verbosity$Super" in client.out


def test_new_config_file(client):
    conf = textwrap.dedent("""\
        tools.microsoft.MSBuild:verbosity=Minimal
        user.mycompany.MyHelper:myconfig=myvalue
        cache:no_locks=True
        cache:read_only=True
        """)
    save(client.cache.new_config_path, conf)
    client.run("install .")
    assert "tools.microsoft.MSBuild$verbosity$Minimal" in client.out
    assert "user.mycompany.MyHelper$myconfig$myvalue" in client.out
    assert "no_locks" not in client.out
    assert "read_only" not in client.out


@patch("conans.client.conf.required_version.client_version", "1.26.0")
def test_new_config_file_required_version():
    client = TestClient()
    conf = textwrap.dedent("""\
        core:required_conan_version=>=2.0
        """)
    save(client.cache.new_config_path, conf)
    with pytest.raises(ConanException) as excinfo:
        client.run("install .")
    assert ("Current Conan version (1.26.0) does not satisfy the defined one (>=2.0)"
            in str(excinfo.value))
