import os
import platform
import textwrap

import pytest
import six
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
                for k, v in self.conf.items():
                    self.output.info("{}${}".format(k, v))
        """)
    client.save({"conanfile.py": conanfile})
    return client


def test_basic_composition(client):
    profile1 = textwrap.dedent("""\
        [conf]
        tools.microsoft.msbuild:verbosity=Quiet
        tools.microsoft.msbuild:performance=Slow
        tools.cmake.cmake:verbosity=Extra
        """)
    profile2 = textwrap.dedent("""\
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal
        tools.microsoft.msbuild:robustness=High
        tools.meson.meson:verbosity=Super
        """)
    client.save({"profile1": profile1,
                 "profile2": profile2})
    client.run("install . -pr=profile1")
    assert "tools.microsoft.msbuild:verbosity$Quiet" in client.out
    assert "tools.microsoft.msbuild:performance$Slow" in client.out
    assert "tools.cmake.cmake:verbosity$Extra" in client.out

    client.run("install . -pr=profile1 -pr=profile2")
    assert "tools.microsoft.msbuild:verbosity$Minimal" in client.out
    assert "tools.microsoft.msbuild:performance$Slow" in client.out
    assert "tools.microsoft.msbuild:robustness$High" in client.out
    assert "tools.cmake.cmake:verbosity$Extra" in client.out
    assert "tools.meson.meson:verbosity$Super" in client.out

    client.run("install . -pr=profile2 -pr=profile1")
    assert "tools.microsoft.msbuild:verbosity$Quiet" in client.out
    assert "tools.microsoft.msbuild:performance$Slow" in client.out
    assert "tools.microsoft.msbuild:robustness$High" in client.out
    assert "tools.cmake.cmake:verbosity$Extra" in client.out
    assert "tools.meson.meson:verbosity$Super" in client.out


def test_basic_inclusion(client):
    profile1 = textwrap.dedent("""\
        [conf]
        tools.microsoft.msbuild:verbosity=Quiet
        tools.microsoft.msbuild:performance=Slow
        tools.cmake.cmake:verbosity=Extra
        """)
    profile2 = textwrap.dedent("""\
        include(profile1)
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal
        tools.microsoft.msbuild:robustness=High
        tools.meson.meson:verbosity=Super
        """)
    client.save({"profile1": profile1,
                 "profile2": profile2})

    client.run("install . -pr=profile2")
    assert "tools.microsoft.msbuild:verbosity$Minimal" in client.out
    assert "tools.microsoft.msbuild:performance$Slow" in client.out
    assert "tools.microsoft.msbuild:robustness$High" in client.out
    assert "tools.cmake.cmake:verbosity$Extra" in client.out
    assert "tools.meson.meson:verbosity$Super" in client.out


def test_composition_conan_conf(client):
    conf = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=Quiet
        tools.microsoft.msbuild:performance=Slow
        tools.cmake.cmake:verbosity=Extra
        """)
    save(client.cache.new_config_path, conf)
    profile = textwrap.dedent("""\
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal
        tools.microsoft.msbuild:robustness=High
        tools.meson.meson:verbosity=Super
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile")
    assert "tools.microsoft.msbuild:verbosity$Minimal" in client.out
    assert "tools.microsoft.msbuild:performance$Slow" in client.out
    assert "tools.microsoft.msbuild:robustness$High" in client.out
    assert "tools.cmake.cmake:verbosity$Extra" in client.out
    assert "tools.meson.meson:verbosity$Super" in client.out


def test_new_config_file(client):
    conf = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=Minimal
        user.mycompany.myhelper:myconfig=myvalue
        *:tools.cmake.cmake:generator=X
        cache:no_locks=True
        cache:read_only=True
        """)
    save(client.cache.new_config_path, conf)
    client.run("install .")
    assert "tools.microsoft.msbuild:verbosity$Minimal" in client.out
    assert "user.mycompany.myhelper:myconfig$myvalue" in client.out
    assert "tools.cmake.cmake:generator$X" in client.out
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


def test_composition_conan_conf_overwritten_by_cli_arg(client):
    conf = textwrap.dedent("""\
        tools.microsoft.msbuild:verbosity=Quiet
        tools.microsoft.msbuild:performance=Slow
        """)
    save(client.cache.new_config_path, conf)
    profile = textwrap.dedent("""\
        [conf]
        tools.microsoft.msbuild:verbosity=Minimal
        tools.microsoft.msbuild:robustness=High
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile -c tools.microsoft.msbuild:verbosity=Detailed "
               "-c tools.meson.meson:verbosity=Super")
    assert "tools.microsoft.msbuild:verbosity$Detailed" in client.out
    assert "tools.microsoft.msbuild:performance$Slow" in client.out
    assert "tools.microsoft.msbuild:robustness$High" in client.out
    assert "tools.meson.meson:verbosity$Super" in client.out


def test_composition_conan_conf_different_data_types_by_cli_arg(client):
    """
    Testing if you want to introduce a list/dict via cli

    >> conan install . -c "tools.build.flags:ccflags+=['-Werror']"
    >> conan install . -c "tools.microsoft.msbuildtoolchain:compile_options={'ExceptionHandling': 'Async'}"

    """
    conf = textwrap.dedent("""\
        tools.build.flags:ccflags=["-Wall"]
        """)
    save(client.cache.new_config_path, conf)
    client.run('install . -c "tools.build.flags:ccflags+=[\'-Werror\']" '
               '-c "tools.microsoft.msbuildtoolchain:compile_options={\'ExceptionHandling\': \'Async\'}"')

    assert "tools.build.flags:ccflags$['-Wall', '-Werror']" in client.out
    assert "tools.microsoft.msbuildtoolchain:compile_options${'ExceptionHandling': 'Async'}" in client.out


@pytest.mark.skipif(six.PY2, reason="only Py3")
def test_jinja_global_conf(client):
    save(client.cache.new_config_path, "user.mycompany:parallel = {{os.cpu_count()/2}}\n"
                                       "user.mycompany:other = {{platform.system()}}\n")
    client.run("install .")
    assert "user.mycompany:parallel={}".format(os.cpu_count()/2) in client.out
    assert "user.mycompany:other={}".format(platform.system()) in client.out
