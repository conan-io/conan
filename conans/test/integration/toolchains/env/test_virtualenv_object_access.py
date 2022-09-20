import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.tools import save


@pytest.fixture
def client():
    client = TestClient()
    conanfile = str(GenConanfile())
    conanfile += """
    def package_info(self):
        self.buildenv_info.define("Foo", "MyVar!")
        self.runenv_info.define("runFoo", "Value!")
        self.buildenv_info.append("Hello", "MyHelloValue!")
    """
    client.save({"conanfile.py": conanfile})
    client.run("create . foo/1.0@")
    save(client.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
    return client


def test_virtualenv_object_access(client):
    conanfile = textwrap.dedent("""
    import os
    from conans import ConanFile
    from conan.tools.env import VirtualBuildEnv, VirtualRunEnv

    class ConanFileToolsTest(ConanFile):
        requires = "foo/1.0"

        def build(self):
          build_env = VirtualBuildEnv(self).vars()
          run_env = VirtualRunEnv(self).vars()
          self.output.warn("Foo: *{}*".format(build_env["Foo"]))
          self.output.warn("runFoo: *{}*".format(run_env["runFoo"]))
          self.output.warn("Hello: *{}*".format(build_env["Hello"]))

          with build_env.apply():
            with run_env.apply():
              self.output.warn("Applied Foo: *{}*".format(os.getenv("Foo", "")))
              self.output.warn("Applied Hello: *{}*".format(os.getenv("Hello", "")))
              self.output.warn("Applied runFoo: *{}*".format(os.getenv("runFoo", "")))
    """)

    profile = textwrap.dedent("""
            [buildenv]
            Foo+=MyFooValue
        """)

    client.save({"conanfile.py": conanfile, "profile": profile})

    client.run("create . app/1.0@ --profile=profile")
    assert "Foo: *MyVar! MyFooValue*"
    assert "runFoo:* Value!*"
    assert "Hello:* MyHelloValue!*"

    assert "Applied Foo: *MyVar! MyFooValue*"
    assert "Applied runFoo: **"
    assert "Applied Hello: * MyHelloValue!*"
