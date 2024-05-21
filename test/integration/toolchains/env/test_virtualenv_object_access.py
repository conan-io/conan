import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


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
    client.run("create . --name=foo --version=1.0")
    return client


def test_virtualenv_object_access(client):
    conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.env import VirtualBuildEnv, VirtualRunEnv

    class ConanFileToolsTest(ConanFile):
        requires = "foo/1.0"

        def build(self):
          build_env = VirtualBuildEnv(self).vars()
          run_env = VirtualRunEnv(self).vars()
          self.output.warning("Foo: *{}*".format(build_env["Foo"]))
          self.output.warning("runFoo: *{}*".format(run_env["runFoo"]))
          self.output.warning("Hello: *{}*".format(build_env["Hello"]))

          with build_env.apply():
            with run_env.apply():
              self.output.warning("Applied Foo: *{}*".format(os.getenv("Foo", "")))
              self.output.warning("Applied Hello: *{}*".format(os.getenv("Hello", "")))
              self.output.warning("Applied runFoo: *{}*".format(os.getenv("runFoo", "")))
    """)

    profile = textwrap.dedent("""
            [buildenv]
            Foo+=MyFooValue
        """)

    client.save({"conanfile.py": conanfile, "profile": profile})

    client.run("create . --name=app --version=1.0 --profile=profile")
    assert "Foo: *MyVar! MyFooValue*"
    assert "runFoo:* Value!*"
    assert "Hello:* MyHelloValue!*"

    assert "Applied Foo: *MyVar! MyFooValue*"
    assert "Applied runFoo: **"
    assert "Applied Hello: * MyHelloValue!*"
