import unittest

from conan.test.utils.tools import TestClient, GenConanfile


class LoopDetectionTest(unittest.TestCase):

    def test_transitive_loop(self):
        client = TestClient(light=True)
        client.save({
            'pkg1.py': GenConanfile().with_require('pkg2/0.1@lasote/stable'),
            'pkg2.py': GenConanfile().with_require('pkg3/0.1@lasote/stable'),
            'pkg3.py': GenConanfile().with_require('pkg1/0.1@lasote/stable'),
        })
        client.run('export pkg1.py --name=pkg1 --version=0.1 --user=lasote --channel=stable')
        client.run('export pkg2.py --name=pkg2 --version=0.1 --user=lasote --channel=stable')
        client.run('export pkg3.py --name=pkg3 --version=0.1 --user=lasote --channel=stable')

        client.run("install --requires=pkg3/0.1@lasote/stable --build='*'", assert_error=True)
        # TODO: Complete with better diagnostics
        self.assertIn("ERROR: There is a cycle/loop in the graph",  client.out)

    def test_self_loop(self):
        client = TestClient(light=True)
        client.save({'pkg1.py': GenConanfile().with_require('pkg1/0.1@lasote/stable'), })
        client.run('export pkg1.py --name=pkg1 --version=0.1 --user=lasote --channel=stable')
        client.run("install --requires=pkg1/0.1@lasote/stable --build='*'", assert_error=True)
        self.assertIn("ERROR: There is a cycle/loop in the graph", client.out)


def test_install_order_infinite_loop():
    c = TestClient(light=True)
    c.save({"fmt/conanfile.py": GenConanfile("fmt", "1.0"),
            "tool/conanfile.py": GenConanfile("tool", "1.0").with_requires("fmt/1.0"),
            "tool_profile": "[tool_requires]\n!tool/*: tool/1.0"})
    c.run("export fmt")
    c.run("export tool")
    c.run("install tool -pr:h=tool_profile -b=missing",
          assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out
    assert "fmt/1.0 (Build) -> ['tool/1.0']" in c.out
    assert "tool/1.0 (Build) -> ['fmt/1.0']" in c.out

    # Graph build-order fails in the same way
    c.run("graph build-order tool -pr:h=tool_profile -b=missing",
          assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out
    assert "fmt/1.0 (Build) -> ['tool/1.0']" in c.out
    assert "tool/1.0 (Build) -> ['fmt/1.0']" in c.out

    c.run("graph build-order tool -pr:h=tool_profile --order-by=configuration -b=missing",
          assert_error=True)
    assert "ERROR: There is a loop in the graph" in c.out
    assert "fmt/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709 (Build) -> " \
           "['tool/1.0:044d18636d2b7da86d3aa46a2aabf1400db525b1']" in c.out
    assert "tool/1.0:044d18636d2b7da86d3aa46a2aabf1400db525b1 (Build) -> " \
           "['fmt/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709']" in c.out
