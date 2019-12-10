import json
import os
import textwrap
import unittest

from conans.model.graph_lock import LOCKFILE, LOCKFILE_VERSION
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer, GenConanfile
from conans.util.env_reader import get_env
from conans.util.files import load


class GraphLockErrorsTest(unittest.TestCase):
    def error_test(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("tool").with_version("0.1")})
        client.run("create .")

        conanfile = textwrap.dedent("""
            from conans import ConanFile 
            class BugTest(ConanFile):
                def test(self):
                    pass
            """)
        client.save({"conanfile.py": GenConanfile().with_name("dep").with_version("0.1"),
                     "test_package/conanfile.py": conanfile,
                     "consumer.txt": "[requires]\ndep/0.1\n",
                     "profile": "[build_requires]\ntool/0.1\n"})

        client.run("export .")
        client.run("graph lock consumer.txt -pr=profile --lockfile bug.lock --build missing")
        lock = client.load("bug.lock")
        print lock
        client.run("create . -pr=profile --lockfile bug.lock --build missing")
        print client.out
