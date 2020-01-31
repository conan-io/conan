import textwrap
import time
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile


class TransitiveHeaderOnlyTest(unittest.TestCase):

    def transitive_header_only_test(self):
        # https://github.com/conan-io/conan/issues/6450
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_version_mode")
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . liba/1.0@")
        client.run("create . liba/2.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("liba/1.0")
                                                   .with_package_id("self.info.header_only()")})
        client.run("create . libb/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libb/1.0")})
        client.run("create . libc/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/1.0")})
        client.run("create . libd/1.0@")
        client.save({"conanfile.py": GenConanfile().with_require_plain("libc/1.0")
                                                   .with_require_plain("liba/2.0")})
        client.run("create . libd/1.0@", assert_error=True)
        self.assertIn("libc/1.0:bfa6c8f046896806f65c8fe554bd57f235b101e8 - Missing", client.out)

