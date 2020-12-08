import json
import unittest
import os


from conans import __version__
from conans.test.utils.tools import TestClient
from conans.util.files import load


class VersionTest(unittest.TestCase):

    def test_version_command(self):
        client = TestClient()
        client.run("version")
        self.assertIn("Conan version %s" % __version__, client.out)

    def test_version_json(self):
        json_file = "version.json"
        client = TestClient()
        client.run("version --json={}".format(json_file))
        self.assertTrue(os.path.isfile(os.path.join(client.current_folder, json_file)))
        json_content = load(os.path.join(client.current_folder, json_file))
        json_data = json.loads(json_content)
        self.assertEqual(json_data["version"], __version__)
