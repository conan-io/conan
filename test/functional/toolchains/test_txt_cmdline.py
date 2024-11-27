import platform
import textwrap
import unittest

import pytest

from conan.test.utils.tools import TestClient


class TestTxtCommandLine(unittest.TestCase):

    def test_declarative(self):
        conanfile = textwrap.dedent("""
            [generators]
            CMakeToolchain
            MesonToolchain
            """)
        client = TestClient()
        client.save({"conanfile.txt": conanfile})
        client.run("install .")
        self._check(client)

    def _check(self, client):
        self.assertIn("conanfile.txt: Generator 'CMakeToolchain' calling 'generate()'", client.out)
        self.assertIn("conanfile.txt: Generator 'MesonToolchain' calling 'generate()'", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("Conan automatically generated toolchain file", toolchain)
        toolchain = client.load("conan_meson_native.ini")
        self.assertIn("[project options]", toolchain)

    def test_command_line(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install . -g CMakeToolchain -g MesonToolchain ")
        self._check(client)


@pytest.mark.tool("visual_studio")
@pytest.mark.skipif(platform.system() != "Windows", reason="Only for windows")
class TestTxtCommandLineMSBuild(unittest.TestCase):

    def test_declarative(self):
        conanfile = textwrap.dedent("""
            [generators]
            MSBuildToolchain
            """)
        client = TestClient()
        client.save({"conanfile.txt": conanfile})
        client.run("install .")
        self._check(client)

    def _check(self, client):
        self.assertIn("conanfile.txt: Generator 'MSBuildToolchain' calling 'generate()'", client.out)
        toolchain = client.load("conantoolchain.props")
        self.assertIn("<?xml version", toolchain)

    def test_command_line(self):
        client = TestClient()
        client.save({"conanfile.txt": ""})
        client.run("install . -g MSBuildToolchain")
        self._check(client)
