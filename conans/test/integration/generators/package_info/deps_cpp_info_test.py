import textwrap
import unittest

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="DepsCppInfo removed")
class DepsCppInfoTest(unittest.TestCase):

    def test(self):
        # https://github.com/conan-io/conan/issues/7598
        client = TestClient()

        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=dep --version=0.1 --user=user --channel=testing")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                requires = "dep/0.1@user/testing"
                def build(self):
                    self.output.info("DEPS_CPP_INFO_BIN: %s" % self.dependencies["dep"].cpp_info.bin_paths)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        self.assertIn("pkg/0.1@user/testing: DEPS_CPP_INFO_BIN: []", client.out)
        client.run("install .")
        client.run("build .")
        self.assertIn("conanfile.py: DEPS_CPP_INFO_BIN: []", client.out)
