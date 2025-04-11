import platform
import textwrap
import os

from conan import conan_version
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.test.utils.env import environment_update


def test_profile_template():
    client = TestClient()
    tpl = textwrap.dedent("""
        [settings]
        os = {{ {"Darwin": "Macos"}.get(platform.system(), platform.system()) }}
        build_type = {{ os.getenv("MY_BUILD_TYPE") }}
        """)
    client.save({"conanfile.py": GenConanfile(),
                 "profile1": tpl})
    with environment_update({"MY_BUILD_TYPE": "Debug"}):
        client.run("install . -pr=profile1")

    current_os = {"Darwin": "Macos"}.get(platform.system(), platform.system())
    assert "os={}".format(current_os)
    assert "build_type=Debug"


def test_profile_template_variables():
    client = TestClient()
    tpl = textwrap.dedent("""
        {% set a = "FreeBSD" %}
        [settings]
        os = {{ a }}
        """)
    client.save({"conanfile.py": GenConanfile(),
                 "profile1": tpl})
    client.run("install . -pr=profile1")
    assert "os=FreeBSD" in client.out


def test_profile_template_import():
    client = TestClient()
    tpl1 = textwrap.dedent("""
        {% import "profile_vars" as vars %}
        [settings]
        os = {{ vars.a }}
        """)
    tpl2 = textwrap.dedent("""
        {% set a = "FreeBSD" %}
        """)
    client.save({"conanfile.py": GenConanfile(),
                 "profile1": tpl1,
                 "profile_vars": tpl2})
    client.run("install . -pr=profile1")
    assert "os=FreeBSD" in client.out


def test_profile_template_import_sibling():
    # https://github.com/conan-io/conan/issues/17431
    client = TestClient()
    tpl1 = textwrap.dedent(r"""
        {% import "sub2/profile_vars" as vars %}
        [settings]
        os = {{ vars.a }}
        """)
    tpl2 = textwrap.dedent("""
        {% set a = "FreeBSD" %}
        """)
    client.save_home({"profiles/sub1/profile1": tpl1,
                      "profiles/sub2/profile_vars": tpl2})
    client.save({"conanfile.py": GenConanfile()})
    client.run("install . -pr=sub1/profile1")
    assert "os=FreeBSD" in client.out


def test_profile_template_include():
    client = TestClient()
    tpl1 = textwrap.dedent("""
        {% include "profile_vars" %}
        """)
    tpl2 = textwrap.dedent("""
        {% set a = "FreeBSD" %}
        [settings]
        os = {{ a }}
        """)
    client.save({"conanfile.py": GenConanfile(),
                 "profile1": tpl1,
                 "profile_vars": tpl2})
    client.run("install . -pr=profile1")
    assert "os=FreeBSD" in client.out


def test_profile_template_include_sibling():
    # https://github.com/conan-io/conan/issues/17431
    client = TestClient()
    tpl1 = textwrap.dedent(r"""
        {% include "sub2/profile_vars" %}
        """)
    tpl2 = textwrap.dedent("""
        {% set a = "FreeBSD" %}
        [settings]
        os = {{ a }}
        """)
    client.save_home({"profiles/sub1/profile1": tpl1,
                      "profiles/sub2/profile_vars": tpl2})
    client.save({"conanfile.py": GenConanfile()})
    client.run("install . -pr=sub1/profile1")
    assert "os=FreeBSD" in client.out


def test_profile_template_include_from_cache():
    # https://github.com/conan-io/conan/issues/17431
    client = TestClient()
    tpl1 = textwrap.dedent(r"""
        {% include "sub2/profile_vars" %}
        """)
    tpl2 = textwrap.dedent("""
        {% set a = "FreeBSD" %}
        [settings]
        os = {{ a }}
        """)
    client.save_home({"profiles/sub2/profile_vars": tpl2})
    client.save({"conanfile.py": GenConanfile(),
                 "sub1/profile1": tpl1})
    client.run("install . -pr=sub1/profile1")
    assert "os=FreeBSD" in client.out


def test_profile_template_profile_dir():
    client = TestClient()
    tpl1 = textwrap.dedent("""
        [conf]
        user.toolchain:mydir = {{ os.path.join(profile_dir, "toolchain.cmake") }}
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import load
        class Pkg(ConanFile):
            def generate(self):
                content = load(self, self.conf.get("user.toolchain:mydir"))
                self.output.info("CONTENT: {}".format(content))
        """)
    client.save({"conanfile.py": conanfile,
                 "anysubfolder/profile1": tpl1,
                 "anysubfolder/toolchain.cmake": "MyToolchainCMake!!!"})
    client.run("install . -pr=anysubfolder/profile1")
    assert "conanfile.py: CONTENT: MyToolchainCMake!!!" in client.out


def test_profile_conf_backslash():
    # https://github.com/conan-io/conan/issues/15726
    c = TestClient()
    profile = textwrap.dedent(r"""
        [conf]
        user.team:myconf = "hello\test"
        """)
    c.save({"profile": profile})
    c.run("profile show -pr=profile")
    assert r"hello\test" in c.out


def test_profile_version():
    client = TestClient()
    tpl1 = textwrap.dedent("""
        [options]
        *:myoption={{conan_version}}
        *:myoption2={{conan_version<13 and conan_version>1.0}}
        """)

    client.save({"conanfile.py": GenConanfile(),
                 "profile1.jinja": tpl1})
    client.run("install . -pr=profile1.jinja")
    assert f"*:myoption={conan_version}" in client.out
    assert "*:myoption2=True" in client.out


def test_profile_template_profile_name():
    """
        The property profile_name should be parsed as the profile file name when rendering profiles
    """
    client = TestClient()
    tpl1 = textwrap.dedent("""
        [conf]
        user.profile:name = {{ profile_name }}
        """)
    tpl2 = textwrap.dedent("""
        include(default)
        [conf]
        user.profile:name = {{ profile_name }}
        """)
    default = textwrap.dedent("""
        [settings]
        os=Windows
        [conf]
        user.profile:name = {{ profile_name }}
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            def configure(self):
                self.output.info("PROFILE NAME: {}".format(self.conf.get("user.profile:name")))
        """)
    client.save({"conanfile.py": conanfile,
                 "profile_folder/foobar": tpl1,
                 "another_folder/foo.profile": tpl1,
                 "include_folder/include_default": tpl2,
                 os.path.join(client.paths.profiles_path, "baz"): tpl1,
                 os.path.join(client.paths.profiles_path, "default"): default})

    # show only file name as profile name
    client.run("install . -pr=profile_folder/foobar")
    assert "conanfile.py: PROFILE NAME: foobar" in client.out

    # profile_name should include file extension
    client.run("install . -pr=another_folder/foo.profile")
    assert "conanfile.py: PROFILE NAME: foo.profile" in client.out

    # default profile should compute profile_name by default too
    client.run("install . -pr=default")
    assert "conanfile.py: PROFILE NAME: default" in client.out

    # profile names should show only their names
    client.run("install . -pr=baz")
    assert "conanfile.py: PROFILE NAME: baz" in client.out

    # included profiles should respect the inherited profile name
    client.run("install . -pr=include_folder/include_default")
    assert "conanfile.py: PROFILE NAME: include_default" in client.out


class TestProfileDetectAPI:
    def test_profile_detect_os_arch(self):
        """ testing OS & ARCH just to test the UX and interface
        """
        client = TestClient()
        tpl1 = textwrap.dedent("""
            [settings]
            os={{detect_api.detect_os()}}
            arch={{detect_api.detect_arch()}}
            """)

        client.save({"profile1": tpl1})
        client.run("profile show -pr=profile1 --context=host")
        pr = client.get_default_host_profile()
        the_os = pr.settings['os']
        arch = pr.settings['arch']
        expected = textwrap.dedent(f"""\
            [settings]
            arch={arch}
            os={the_os}
            """)
        assert expected in client.out

    def test_profile_detect_compiler_missing_error(self):
        client = TestClient(light=True)
        tpl1 = textwrap.dedent("""
                    {% set compiler, version, compiler_exe = detect_api.detect_clang_compiler(compiler_exe="not-existing-compiler") %}
                    {% set version = detect_api.default_compiler_version(compiler, version) %}
                    """)

        client.save({"profile1": tpl1})
        client.run("profile show -pr=profile1", assert_error=True)
        assert "No version provided to 'detect_api.default_compiler_version()' for None compiler" in client.out


def test_profile_jinja_error():
    c = TestClient(light=True)
    profile = textwrap.dedent("""
        {% set arr = [
            {# comment that triggers the error #}
            'smth'
        ] %}""")
    c.save({"profile1": profile,
            "profile2": "include(profile1)",
            "profile3": "include(profile2)",
            "conanfile.txt": ""})
    c.run("profile show -pr=profile1", assert_error=True)
    assert "ERROR: Error while rendering the profile template file" in c.out
    c.run("profile show -pr=profile2", assert_error=True)
    assert "ERROR: Error reading 'profile2' profile: Error while " \
           "rendering the profile template file " in c.out
    assert "unexpected char '#' at 21" in c.out
    c.run("profile show -pr=profile3", assert_error=True)
    assert "ERROR: Error reading 'profile3' profile: Error reading 'profile2' profile: Error while " \
           "rendering the profile template file " in c.out
    assert "unexpected char '#' at 21" in c.out

    # Also install messages
    c.run("install . -pr=profile1", assert_error=True)
    assert "ERROR: Error while rendering the profile template file" in c.out
    assert "unexpected char '#' at 21" in c.out

    c.run("install . -pr=profile2", assert_error=True)
    assert "ERROR: Error reading 'profile2' profile: Error while " \
           "rendering the profile template file " in c.out
    assert "unexpected char '#' at 21" in c.out
    c.run("install . -pr=profile3", assert_error=True)
    assert "ERROR: Error reading 'profile3' profile: Error reading 'profile2' profile: Error while " \
           "rendering the profile template file " in c.out
    assert "unexpected char '#' at 21" in c.out


def test_profile_macro_per_package():
    client = TestClient()
    tpl1 = textwrap.dedent("""
        {% macro set_windows_settings(lib) %}
        {{lib}}/*:os=Windows
        {{lib}}/*:arch=x86
        {% endmacro %}
        {% macro set_windows_conf(lib) %}
        {{lib}}/*:user.conf:key = 2
        {% endmacro %}

        [settings]
        os = Linux
        {{set_windows_settings("mypkg")}}
        [conf]
        user.conf:key = 1
        {{set_windows_conf("mypkg")}}
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "mypkg"
            version = "0.1"
            settings = "os", "arch"
            def generate(self):
                value = self.conf.get("user.conf:key")
                self.output.info(f"os={self.settings.os}!!")
                self.output.info(f"arch={self.settings.arch}!!")
                self.output.info(f"user.conf:key={value}!!!!")
        """)
    client.save({"conanfile.py": conanfile,
                 "profile1": tpl1})
    client.run("install . -pr=profile1")
    assert "conanfile.py (mypkg/0.1): user.conf:key=2!!!!" in client.out
    assert "conanfile.py (mypkg/0.1): os=Windows!!" in client.out
    assert "conanfile.py (mypkg/0.1): arch=x86!!" in client.out
