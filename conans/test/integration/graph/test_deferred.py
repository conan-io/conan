
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_deferred():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_tool_requires("tool/1.0"),
                 "profile": "[deferred_requires]\ntool/1.0"})
    client.run("create . pkg/1.0@ -pr=profile")
    assert "tool/1.0:357add7d387f11a959f3ee7d4fc9c2487dbaa604 - Deferred" in client.out
