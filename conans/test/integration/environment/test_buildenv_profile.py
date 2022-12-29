import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    conanfile = textwrap.dedent("""
       from conans import ConanFile
       class Pkg(ConanFile):
           def generate(self):
               for var in (1, 2):
                   v = self.buildenv.vars(self).get("MyVar{}".format(var))
                   self.output.info("MyVar{}={}!!".format(var, v))
       """)
    profile1 = textwrap.dedent("""
      [buildenv]
      MyVar1=MyValue1_1
      MyVar2=MyValue2_1
      """)
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "profile1": profile1})
    return client


def test_buildenv_profile_cli(client):
    profile2 = textwrap.dedent("""
        [buildenv]
        MyVar1=MyValue1_2
        MyVar2+=MyValue2_2
        """)
    client.save({"profile2": profile2})

    client.run("install . -pr=profile1 -pr=profile2")
    assert "conanfile.py: MyVar1=MyValue1_2!!" in client.out
    assert "conanfile.py: MyVar2=MyValue2_1 MyValue2_2" in client.out


def test_buildenv_profile_include(client):
    profile2 = textwrap.dedent("""
        include(profile1)
        [buildenv]
        MyVar1=MyValue1_2
        MyVar2+=MyValue2_2
        """)
    client.save({"profile2": profile2})

    client.run("install . -pr=profile2")
    assert "conanfile.py: MyVar1=MyValue1_2!!" in client.out
    assert "conanfile.py: MyVar2=MyValue2_1 MyValue2_2" in client.out
