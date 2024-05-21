import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    conanfile = textwrap.dedent("""
       from conan import ConanFile
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


def test_buildenv_package_patterns():
    client = TestClient()
    conanfile = GenConanfile()
    generate = """
    def generate(self):
        value = self.buildenv.vars(self).get("my_env_var") or "None"
        self.output.warning("{} ENV:{}".format(self.ref.name, value))
"""
    client.save({"dep/conanfile.py": str(conanfile) + generate,
                 "pkg/conanfile.py": str(conanfile.with_requirement("dep/0.1", visible=False)) + generate,
                 "consumer/conanfile.py": str(conanfile.with_requires("pkg/0.1")
                .with_settings("os", "build_type", "arch")) + generate})

    client.run("export dep --name=dep --version=0.1")
    client.run("export pkg --name=pkg --version=0.1")

    # This pattern applies to no package
    profile = """
            include(default)
            [buildenv]
            invented/*:my_env_var=Foo
            """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep ENV:None" in client.out
    assert "WARN: pkg ENV:None" in client.out
    assert "WARN: None ENV:None" in client.out

    # This patterns applies to dep
    profile = """
                include(default)
                [buildenv]
                dep/*:my_env_var=Foo
                """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep ENV:Foo" in client.out
    assert "WARN: pkg ENV:None" in client.out
    assert "WARN: None ENV:None" in client.out

    profile = """
                    include(default)
                    [buildenv]
                    dep/0.1:my_env_var=Foo
                    """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep ENV:Foo" in client.out
    assert "WARN: pkg ENV:None" in client.out
    assert "WARN: None ENV:None" in client.out

    # The global pattern applies to all
    profile = """
                    include(default)
                    [buildenv]
                    dep/*:my_env_var=Foo
                    pkg/*:my_env_var=Foo
                    my_env_var=Var
                    """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep ENV:Var" in client.out
    assert "WARN: pkg ENV:Var" in client.out
    assert "WARN: None ENV:Var" in client.out

    # "&" pattern for the consumer
    profile = """
                        include(default)
                        [buildenv]
                        dep/*:my_env_var=Foo
                        pkg/*:my_env_var=Foo2
                        &:my_env_var=Var
                        """
    client.save({"profile": profile})
    client.run("install consumer --build='*' --profile profile")
    assert "WARN: dep ENV:Foo" in client.out
    assert "WARN: pkg ENV:Foo2" in client.out
    assert "WARN: None ENV:Var" in client.out
