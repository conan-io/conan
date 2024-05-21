import os
import platform
import textwrap

import pytest
from mock import patch

from conan import conan_version
from conan.internal.api import detect_api
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conans.util.files import save, load
from conan.test.utils.tools import TestClient


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
        tools.build:verbosity=quiet
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
    assert "tools.build:verbosity$quiet" in client.out
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
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:max_cpu_count=High
        tools.meson.mesontoolchain:backend=Super
        """)
    client.save({"profile1": profile1,
                 "profile2": profile2})

    client.run("install . -pr=profile2")
    assert "tools.build:verbosity$quiet" in client.out
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
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:max_cpu_count=High
        tools.meson.mesontoolchain:backend=Super
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile")
    assert "tools.build:verbosity$quiet" in client.out
    assert "tools.microsoft.msbuild:vs_version$Slow" in client.out
    assert "tools.microsoft.msbuild:max_cpu_count$High" in client.out
    assert "tools.cmake.cmaketoolchain:generator$Extra" in client.out
    assert "tools.meson.mesontoolchain:backend$Super" in client.out


def test_new_config_file(client):
    conf = textwrap.dedent("""\
        tools.build:verbosity=quiet
        user.mycompany.myhelper:myconfig=myvalue
        *:tools.cmake.cmaketoolchain:generator=X
        """)
    save(client.cache.new_config_path, conf)
    client.run("install .")
    assert "tools.build:verbosity$quiet" in client.out
    assert "user.mycompany.myhelper:myconfig$myvalue" in client.out
    assert "tools.cmake.cmaketoolchain:generator$X" in client.out
    assert "read_only" not in client.out

    conf = textwrap.dedent("""\
            tools.build:verbosity=notice
            user.mycompany.myhelper:myconfig=myvalue
            *:tools.cmake.cmaketoolchain:generator=X
            cache:read_only=True
            """)
    save(client.cache.new_config_path, conf)
    client.run("install .", assert_error=True)
    assert "[conf] Either 'cache:read_only' does not exist in configuration list" in client.out


@patch("conans.client.conf.required_version.client_version", "1.26.0")
def test_new_config_file_required_version():
    client = TestClient()
    conf = textwrap.dedent("""\
        core:required_conan_version=>=2.0
        """)
    save(client.cache.new_config_path, conf)
    client.run("install .", assert_error=True)
    assert ("Current Conan version (1.26.0) does not satisfy the defined one (>=2.0)"
            in client.out)


def test_composition_conan_conf_overwritten_by_cli_arg(client):
    conf = textwrap.dedent("""\
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:max_cpu_count=Slow
        """)
    save(client.cache.new_config_path, conf)
    profile = textwrap.dedent("""\
        [conf]
        tools.build:verbosity=quiet
        tools.microsoft.msbuild:vs_version=High
        """)
    client.save({"profile": profile})
    client.run("install . -pr=profile -c tools.build:verbosity=verbose "
               "-c tools.meson.mesontoolchain:backend=Super")
    assert "tools.build:verbosity$verbose" in client.out
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
    cache_folder = c.cache_folder.replace("\\", "/")
    assert f"user.mycompany:myfile: {os.path.join(cache_folder, 'myfile')}" in c.out


def test_profile_detect_os_arch():
    """ testing OS & ARCH just to test that detect_api is injected
    """
    c = TestClient()
    global_conf = textwrap.dedent("""
        user.myteam:myconf1={{detect_api.detect_os()}}
        user.myteam:myconf2={{detect_api.detect_arch()}}
        """)

    save(c.cache.new_config_path, global_conf)
    c.run("config show *")
    _os = detect_api.detect_os()
    _arch = detect_api.detect_arch()
    assert f"user.myteam:myconf1: {_os}" in c.out
    assert f"user.myteam:myconf2: {_arch}" in c.out


def test_empty_conf_valid():
    tc = TestClient()
    profile = textwrap.dedent(r"""
    [conf]
    user:unset=
    """)
    conanfile = textwrap.dedent(r"""
    from conan import ConanFile

    class BasicConanfile(ConanFile):
        name = "pkg"
        version = "1.0"

        def generate(self):
            self.output.warning(f'My unset conf variable is: "{self.conf.get("user:unset")}"')
            self.output.warning(f'My unset conf is {"NOT" if self.conf.get("user:unset") == None else ""} set')
    """)
    tc.save({"conanfile.py": conanfile, "profile": profile})

    tc.run("create .")
    assert 'pkg/1.0: WARN: My unset conf is NOT set' in tc.out

    tc.run("create . -pr=profile")
    assert 'pkg/1.0: WARN: My unset conf variable is: ""' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out

    tc.run("create . -c user:unset=")
    assert 'pkg/1.0: WARN: My unset conf variable is: ""' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out

    tc.run('create . -c user:unset=""')
    assert 'pkg/1.0: WARN: My unset conf variable is: ""' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out

    # And ensure this actually works for the normal case, just in case
    tc.run("create . -c user:unset=Hello")
    assert 'pkg/1.0: WARN: My unset conf variable is: "Hello"' in tc.out
    assert 'pkg/1.0: WARN: My unset conf is  set' in tc.out


def test_nonexisting_conf():
    c = TestClient()
    c.save({"conanfile.txt": ""})
    c.run("install . -c tools.unknown:conf=value", assert_error=True)
    assert "ERROR: [conf] Either 'tools.unknown:conf' does not exist in configuration" in c.out
    c.run("install . -c user.some:var=value")  # This doesn't fail
    c.run("install . -c tool.build:verbosity=v", assert_error=True)
    assert "ERROR: [conf] Either 'tool.build:verbosity' does not exist in configuration" in c.out


def test_nonexisting_conf_global_conf():
    c = TestClient()
    save(c.cache.new_config_path, "tools.unknown:conf=value")
    c.save({"conanfile.txt": ""})
    c.run("install . ", assert_error=True)
    assert "ERROR: [conf] Either 'tools.unknown:conf' does not exist in configuration" in c.out


def test_global_conf_auto_created():
    c = TestClient()
    c.run("config list")  # all commands will trigger
    global_conf = load(c.cache.new_config_path)
    assert "# core:non_interactive = True" in global_conf


def test_command_line_core_conf():
    c = TestClient()
    c.run("config show * -cc core:default_profile=potato")
    assert "core:default_profile: potato" in c.out
    c.run("config show * -cc core:default_profile=potato -cc core:default_build_profile=orange")
    assert "core:default_profile: potato" in c.out
    assert "core:default_build_profile: orange" in c.out

    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("export .")

    tfolder = temp_folder()
    c.run(f'list * -cc core.cache:storage_path="{tfolder}"')
    assert "WARN: There are no matching recipe references" in c.out
    c.run(f'list *')
    assert "WARN: There are no matching recipe references" not in c.out
    assert "pkg/0.1" in c.out

    c.run("list * -cc user.xxx:yyy=zzz", assert_error=True)
    assert "ERROR: Only core. values are allowed in --core-conf. Got user.xxx:yyy=zzz" in c.out


def test_build_test_consumer_only():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def generate(self):
                skip = self.conf.get("tools.build:skip_test", check_type=bool)
                self.output.info(f'SKIP-TEST: {skip}')
        """)
    pkg = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                requires = "dep/0.1"
                def generate(self):
                    self.output.info(f'SKIP-TEST: {self.conf.get("tools.build:skip_test")}')
            """)
    save(c.cache.new_config_path, "tools.build:skip_test=True\n&:tools.build:skip_test=False")
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": pkg,
            "pkg/test_package/conanfile.py": GenConanfile().with_test("pass")})
    c.run("create dep")
    assert "dep/0.1: SKIP-TEST: False" in c.out
    c.run('create pkg --build=* -tf=""')
    assert "dep/0.1: SKIP-TEST: True" in c.out
    assert "pkg/0.1: SKIP-TEST: False" in c.out
    c.run('create pkg --build=*')
    assert "dep/0.1: SKIP-TEST: True" in c.out
    assert "pkg/0.1: SKIP-TEST: False" in c.out
    c.run('install pkg --build=*')
    assert "dep/0.1: SKIP-TEST: True" in c.out
    assert "conanfile.py (pkg/0.1): SKIP-TEST: False" in c.out


def test_conf_should_be_immutable():
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"
            def generate(self):
                self.conf.append("user.myteam:myconf", "value1")
                self.output.info(f'user.myteam:myconf: {self.conf.get("user.myteam:myconf")}')
        """)
    pkg = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            requires = "dep/0.1"
            def generate(self):
                self.output.info(f'user.myteam:myconf: {self.conf.get("user.myteam:myconf")}')
        """)
    save(c.cache.new_config_path, 'user.myteam:myconf=["root_value"]')
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": pkg})
    c.run("create dep")
    assert "dep/0.1: user.myteam:myconf: ['root_value', 'value1']" in c.out
    c.run('create pkg --build=*')
    assert "dep/0.1: user.myteam:myconf: ['root_value', 'value1']" in c.out
    # The pkg/0.1 output should be non-modified
    assert "pkg/0.1: user.myteam:myconf: ['root_value']" in c.out


def test_especial_strings_fail():
    # https://github.com/conan-io/conan/issues/15777
    c = TestClient()
    global_conf = textwrap.dedent("""
        user.mycompany:myfile = re
        user.mycompany:myother = fnmatch
        user.mycompany:myfunct = re.search
        user.mycompany:mydict = {1: 're', 2: 'fnmatch'}
        """)
    save(c.cache.new_config_path, global_conf)
    c.run("config show *")
    assert "user.mycompany:myfile: re" in c.out
    assert "user.mycompany:myother: fnmatch" in c.out
    assert "user.mycompany:myfunct: re.search" in c.out
    assert "user.mycompany:mydict: {1: 're', 2: 'fnmatch'}" in c.out
