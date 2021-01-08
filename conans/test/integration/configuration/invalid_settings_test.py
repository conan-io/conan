import os
import textwrap
import unittest

from conans.test.utils.tools import TestClient


class SettingsLoadTestCase(unittest.TestCase):
    def test_invalid_settings(self):
        client = TestClient()
        client.save({os.path.join(client.cache_folder, 'settings.yml'): """your buggy file"""})
        client.run("new -b hello/1.0")
        client.run("install .", assert_error=True)
        self.assertIn("ERROR: Invalid settings.yml format", client.out)

    def test_invalid_yaml(self):
        client = TestClient()
        client.save({os.path.join(client.cache_folder, 'settings.yml'):
                     textwrap.dedent("""
                        Almost:
                            - a
                            - valid
                          yaml
                     """)})
        client.run("new -b hello/1.0")
        client.run("install .", assert_error=True)
        self.assertIn("ERROR: Invalid settings.yml format: while parsing a block mapping",
                      client.out)
