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
        client.run('export pkg1.py pkg1/0.1@lasote/stable')
        client.run('export pkg2.py pkg2/0.1@lasote/stable')
        client.run('export pkg3.py pkg3/0.1@lasote/stable')

        client.run("install pkg3/0.1@lasote/stable --build", assert_error=True)
        self.assertIn("ERROR: Loop detected in context host: 'pkg2/0.1@lasote/stable' requires "
                      "'pkg3/0.1@lasote/stable' which is an ancestor too",
                      client.out)

    def test_self_loop(self):
        client = TestClient()
        client.save({'pkg1.py': GenConanfile().with_require('pkg1/0.1@lasote/stable'), })
        client.run('export pkg1.py pkg1/0.1@lasote/stable')
        client.run("install pkg1/0.1@lasote/stable --build", assert_error=True)
        self.assertIn("ERROR: Loop detected in context host: 'pkg1/0.1@lasote/stable' requires "
                      "'pkg1/0.1@lasote/stable' which is an ancestor too",
                      client.out)
