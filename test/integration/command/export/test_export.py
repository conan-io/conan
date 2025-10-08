import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_basic():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "hello"
            version = "1.2"
            user = "myuser"
            channel = "mychannel"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export .")
    assert "hello/1.2@myuser/mychannel" in client.out
    client.run("list *")
    assert "hello/1.2@myuser/mychannel" in client.out
    client.run("create .")
    assert "hello/1.2@myuser/mychannel" in client.out
    assert "hello/1.2:" not in client.out



def test_export_cci():
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("mypkg", "cci.123")})
    c.run("export .")
    assert ("WARN: risk: Version 'cci.123' contains an alphanumeric "
            "major alongside a minor version") in c.out

    c.save({"conanfile.py": GenConanfile("mypkg", "develop")})
    c.run("export .")
    assert "WARN" not in c.out

    c.save({"conanfile.py": GenConanfile("mypkg", "cci.123")
           .with_class_attribute("package_id_embed_mode='full_mode'")})
    c.run("export .")
    assert "WARN" not in c.out
