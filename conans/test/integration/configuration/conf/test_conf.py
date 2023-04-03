import os
import platform
import textwrap

import pytest
from mock import patch

from conan import conan_version
from conans.errors import ConanException
from conans.util.files import save
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

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
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:vs_version=Slow
        tools.cmake.cmaketoolchain:generator=Extra
        """)
    profile2 = textwrap.dedent("""\
        [conf]
        tools.build:verbosity=notice
        tools.microsoft.msbuild:max_cpu_count=High
        tools.meson.mesontoolchain:backend=Super
        """)
    client.save({"profile1": profile1,
                 "profile2": profile2})
    client.run("install . -pr=profile1")
    assert "tools.build:verbosity$quiet" in client.out
    assert "tools.microsoft.msbuild:vs_version$Slow" in client.out
    assert "tools.cmake.cmaketoolchain:generator$Extra" in client.out

    client.run("install . -pr=profile1 -pr=profile2")
    assert "tools.build:verbosity$notice" in client.out
    assert "tools.microsoft.msbuild:vs_version$Slow" in client.out
    assert "tools.microsoft.msbuild:max_cpu_count$High" in client.out
    assert "tools.cmake.cmaketoolchain:generator$Extra" in client.out
    assert "tools.meson.mesontoolchain:backend$Super" in client.out

    client.run("install . -pr=profile2 -pr=profile1")
    assert "tools.build:verbosity$quiet" in client.out
    assert "tools.microsoft.msbuild:vs_version$Slow" in client.out
    assert "tools.microsoft.msbuild:max_cpu_count$High" in client.out
    assert "tools.cmake.cmaketoolchain:generator$Extra" in client.out
    assert "tools.meson.mesontoolchain:backend$Super" in client.out


def test_basic_inclusion(client):
    profile1 = textwrap.dedent("""\
        [conf]
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:vs_version=Slow
        tools.cmake.cmaketoolchain:generator=Extra
        """)
    profile2 = textwrap.dedent("""\
        include(profile1)
        [conf]
        tools.build:verbosity=notice
        tools.microsoft.msbuild:max_cpu_count=High
        tools.meson.mesontoolchain:backend=Super
        """)
    client.save({"profile1": profile1,
                 "profile2": profile2})

    client.run("install . -pr=profile2")
    assert "tools.build:verbosity$notice" in client.out
    assert "tools.microsoft.msbuild:vs_version$Slow" in client.out
    assert "tools.microsoft.msbuild:max_cpu_count$High" in client.out
    assert "tools.cmake.cmaketoolchain:generator$Extra" in client.out
    assert "tools.meson.mesontoolchain:backend$Super" in client.out


def test_composition_conan_conf(client):
    conf = textwrap.dedent("""\
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:vs_version=Slow
        tools.cmake.cmaketoolchain:generator=Extra
        """)
    save(client.cache.new_config_path, conf)
    profile = textwrap.dedent("""\
        [conf]
        tools.build:verbosity=notice
        tools.microsoft.msbuild:max_cpu_count=High
        tools.meson.mesontoolchain:backend=Super
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile")
    assert "tools.build:verbosity$notice" in client.out
    assert "tools.microsoft.msbuild:vs_version$Slow" in client.out
    assert "tools.microsoft.msbuild:max_cpu_count$High" in client.out
    assert "tools.cmake.cmaketoolchain:generator$Extra" in client.out
    assert "tools.meson.mesontoolchain:backend$Super" in client.out


def test_new_config_file(client):
    conf = textwrap.dedent("""\
        tools.build:verbosity=notice
        user.mycompany.myhelper:myconfig=myvalue
        *:tools.cmake.cmaketoolchain:generator=X
        cache:read_only=True
        """)
    save(client.cache.new_config_path, conf)
    client.run("install .")
    assert "tools.build:verbosity$notice" in client.out
    assert "user.mycompany.myhelper:myconfig$myvalue" in client.out
    assert "tools.cmake.cmaketoolchain:generator$X" in client.out
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
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:max_cpu_count=Slow
        """)
    save(client.cache.new_config_path, conf)
    profile = textwrap.dedent("""\
        [conf]
        tools.build:verbosity=notice
        tools.microsoft.msbuild:vs_version=High
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile -c tools.build:verbosity=debug "
               "-c tools.meson.mesontoolchain:backend=Super")
    assert "tools.build:verbosity$debug" in client.out
    assert "tools.microsoft.msbuild:max_cpu_count$Slow" in client.out
    assert "tools.microsoft.msbuild:vs_version$High" in client.out
    assert "tools.meson.mesontoolchain:backend$Super" in client.out


def test_composition_conan_conf_different_data_types_by_cli_arg(client):
    """
    Testing if you want to introduce a list/dict via cli

    >> conan install . -c "tools.build.flags:ccflags+=['-Werror']"
    >> conan install . -c "tools.microsoft.msbuildtoolchain:compile_options={'ExceptionHandling': 'Async'}"

    """
    conf = textwrap.dedent("""\
        tools.build:cflags=["-Wall"]
        """)
    save(client.cache.new_config_path, conf)
    client.run('install . -c "tools.build:cflags+=[\'-Werror\']" '
               '-c "tools.microsoft.msbuildtoolchain:compile_options={\'ExceptionHandling\': \'Async\'}"')

    assert "tools.build:cflags$['-Wall', '-Werror']" in client.out
    assert "tools.microsoft.msbuildtoolchain:compile_options${'ExceptionHandling': 'Async'}" in client.out


def test_jinja_global_conf(client):
    save(client.cache.new_config_path, "user.mycompany:parallel = {{os.cpu_count()/2}}\n"
                                       "user.mycompany:other = {{platform.system()}}\n"
                                       "user.mycompany:dist = {{distro.id() if distro else '42'}}\n"
                                       "user.conan:version = {{conan_version}}-{{conan_version>0.1}}")
    client.run("install .")
    assert "user.mycompany:parallel={}".format(os.cpu_count()/2) in client.out
    assert "user.mycompany:other={}".format(platform.system()) in client.out
    assert f"user.conan:version={conan_version}-True" in client.out
    if platform.system() == "Linux":
        import distro
        assert "user.mycompany:dist={}".format(distro.id()) in client.out
    else:
        assert "user.mycompany:dist=42" in client.out


def test_jinja_global_conf_include(client):
    global_conf = textwrap.dedent("""\
        {% include "user_global.conf" %}
        {% import "user_global.conf" as vars %}
        user.mycompany:dist = {{vars.myvar*2}}
        """)
    user_global_conf = textwrap.dedent("""\
        {% set myvar = 42 %}
        user.mycompany:parallel = {{myvar}}
        """)
    save(client.cache.new_config_path, global_conf)
    save(os.path.join(client.cache_folder, "user_global.conf"), user_global_conf)
    client.run("install .")
    assert "user.mycompany:parallel=42" in client.out
    assert "user.mycompany:dist=84" in client.out


def test_jinja_global_conf_paths():
    c = TestClient()
    global_conf = 'user.mycompany:myfile = {{os.path.join(conan_home_folder, "myfile")}}'
    save(c.cache.new_config_path, global_conf)
    c.run("config show *")
    assert f"user.mycompany:myfile: {os.path.join(c.cache_folder, 'myfile')}" in c.out


def test_empty_conf_valid():
    tc = TestClient()
    profile = textwrap.dedent(r"""
    [conf]
    user.unset=
    """)
    conanfile = textwrap.dedent(r"""
    from conan import ConanFile

    class BasicConanfile(ConanFile):
        name = "pkg"
        version = "1.0"

        def generate(self):
            self.output.warning(f'My unset conf variable is: "{self.conf.get("user.unset")}"')
            self.output.warning(f'My unset conf is {"NOT" if self.conf.get("user.unset") == None else ""} set')
    """)
    tc.save({"conanfile.py": conanfile, "profile": profile})

    tc.run("create .")
    assert 'pkg/1.0: WARN: My unset conf is NOT set' in tc.out

    tc.run("create . -pr=profile")
    assert 'pkg/1.0: WARN: My unset conf variable is: ""' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out

    tc.run("create . -c user.unset=")
    assert 'pkg/1.0: WARN: My unset conf variable is: ""' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out

    tc.run('create . -c user.unset=""')
    assert 'pkg/1.0: WARN: My unset conf variable is: ""' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out

    # And ensure this actually works for the normal case, just in case
    tc.run("create . -c user.unset=Hello")
    assert 'pkg/1.0: WARN: My unset conf variable is: "Hello"' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out


def test_nonexisting_conf():
    c = TestClient()
    c.save({"conanfile.txt": ""})
    c.run("install . -c tools.unknown:conf=value", assert_error=True)
    assert "ERROR: Unknown conf 'tools.unknown:conf'" in c.out
    c.run("install . -c user.some:var=value")  # This doesn't fail


def test_nonexisting_conf_global_conf():
    c = TestClient()
    save(c.cache.new_config_path, "tools.unknown:conf=value")
    c.save({"conanfile.txt": ""})
    c.run("install . ", assert_error=True)
    assert "ERROR: Unknown conf 'tools.unknown:conf'" in c.out
