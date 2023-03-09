import platform
import textwrap

from conan import conan_version
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.env import environment_update


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
