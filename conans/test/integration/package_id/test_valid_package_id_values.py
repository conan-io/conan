import json
import textwrap


from conans.cli.exit_codes import ERROR_INVALID_CONFIGURATION
from conans.client.graph.graph import BINARY_INVALID
from conans.test.assets.genconanfile import GenConanfile
from conans.util.files import save
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class TestValidPackageIdValue:

    def test_valid(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                options = {"shared": [False, True]}
            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . --name=pkg --version=0.1")


