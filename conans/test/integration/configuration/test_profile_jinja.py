import platform
import textwrap

from conans.client.tools import environment_append
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_profile_template():
    client = TestClient()
    tpl = textwrap.dedent("""
        [settings]
        os = {{ {"Darwin": "Macos"}.get(platform.system(), platform.system()) }}
        build_type = {{ os.getenv("MY_BUILD_TYPE") }}
        """)
    client.save({"conanfile.py": GenConanfile(),
                 "profile1.jinja": tpl})
    with environment_append({"MY_BUILD_TYPE": "Debug"}):
        client.run("install . -pr=profile1.jinja")

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
                 "profile1.jinja": tpl})
    client.run("install . -pr=profile1.jinja")
    assert "os=FreeBSD" in client.out


def test_profile_template_inclusion():
    client = TestClient()
    tpl1 = textwrap.dedent("""
        {% import "profile_vars.jinja" as vars %}
        [settings]
        os = {{ vars.a }}
        """)
    tpl2 = textwrap.dedent("""
        {% set a = "FreeBSD" %}
        """)
    client.save({"conanfile.py": GenConanfile(),
                 "profile1.jinja": tpl1,
                 "profile_vars.jinja": tpl2})
    client.run("install . -pr=profile1.jinja")
    assert "os=FreeBSD" in client.out


def test_profile_template_profile_dir():
    client = TestClient()
    tpl1 = textwrap.dedent("""
        [conf]
        tools.toolchain:mydir = {{ os.path.join(profile_dir, "toolchain.cmake") }}
        """)
    conanfile = textwrap.dedent("""
        from conans import ConanFile, load
        class Pkg(ConanFile):
            def generate(self):
                content = load(self.conf["tools.toolchain:mydir"])
                self.output.info("CONTENT: {}".format(content))
        """)
    client.save({"conanfile.py": conanfile,
                 "anysubfolder/profile1.jinja": tpl1,
                 "anysubfolder/toolchain.cmake": "MyToolchainCMake!!!"})
    client.run("install . -pr=anysubfolder/profile1.jinja")
    assert "conanfile.py: CONTENT: MyToolchainCMake!!!" in client.out
