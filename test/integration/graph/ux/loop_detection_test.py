import unittest

from conans.test.utils.tools import TestClient, GenConanfile


class LoopDetectionTest(unittest.TestCase):

    def test_transitive_loop(self):
        client = TestClient()
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
        client = TestClient()
        client.save({'pkg1.py': GenConanfile().with_require('pkg1/0.1@lasote/stable'), })
        client.run('export pkg1.py --name=pkg1 --version=0.1 --user=lasote --channel=stable')
        client.run("install --requires=pkg1/0.1@lasote/stable --build='*'", assert_error=True)
        self.assertIn("ERROR: There is a cycle/loop in the graph", client.out)
