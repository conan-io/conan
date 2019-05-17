import textwrap
import unittest
from collections import OrderedDict

from conans.test.utils.tools import TestClient, TestServer


class InstallIncompleteRefs(unittest.TestCase):

    def setUp(self):
        self.server = TestServer(users={"user": "password"}, write_permissions=[("*/*@*/*", "*")])
        servers = OrderedDict([("default", self.server)])
        self.client = TestClient(servers=servers, users={"default": [("user", "password")]})

    def install_without_ref_test(self):

        conanfile = textwrap.dedent("""
                from conans import ConanFile

                class MyPkg(ConanFile):
                    name = "lib"
                    version = "1.0"
                """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run('create .')
        self.client.run('upload lib/1.0 -c --all')
        self.client.run('remove "*" -f')
        self.client.run('install lib/1.0@')
        self.assertIn("lib/1.0: Downloaded", self.client.out)

        # This fails, it think it is a path
        self.client.run('install lib/1.0', assert_error=True)

        # Try this syntax to upload too
        self.client.run('upload lib/1.0@ -c --all')
