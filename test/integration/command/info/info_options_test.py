from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_info_options():
    # packages with dash
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("my-package", "1.3")
                .with_option("shared", [True, False])
                .with_default_option("shared", False)})

    # local
    client.run("graph info .")
    assert "shared: False" in client.out
    client.run("graph info . -o shared=True")
    assert "shared: True" in client.out
    client.run("graph info . -o my-package*:shared=True")
    assert "shared: True" in client.out

    # in cache
    client.run("export .")
    client.run("graph info --requires=my-package/1.3")
    assert "shared: False" in client.out
    client.run("graph info --requires=my-package/1.3 -o shared=True")
    assert "shared: True" in client.out
    client.run("graph info --requires=my-package/1.3 -o my-package*:shared=True")
    assert "shared: True" in client.out

