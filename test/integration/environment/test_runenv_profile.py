import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    conanfile = textwrap.dedent("""
       from conan import ConanFile
       class Pkg(ConanFile):
           generators = "VirtualRunEnv"
           def generate(self):
               for var in (1, 2):
                   v = self.runenv.vars(self).get("MyVar{}".format(var))
                   self.output.info("MyVar{}={}!!".format(var, v))
       """)
    profile1 = textwrap.dedent("""
      [runenv]
      MyVar1=MyValue1_1
      MyVar2=MyValue2_1
      """)
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "profile1": profile1})
    return client


def test_buildenv_profile_cli(client):
    client.run("install . -pr=profile1")
    assert "conanfile.py: MyVar1=MyValue1_1!!" in client.out
    assert "conanfile.py: MyVar2=MyValue2_1!!" in client.out
    env = client.load("conanrunenv.sh")
    assert "MyValue1_1" in env
    assert "MyValue2_1" in env
