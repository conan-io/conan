# -*- coding: utf-8 -*-

import json
import os
import textwrap
import unittest

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.mark.xfail(reason="Rethink cache generators for conan 2.0")
class GeneratorFromCacheTest(unittest.TestCase):
    """
    Tests user defined generators loaded from the generators folder in
    the client cache.
    """
    # FIXME: We need to address the generators in cache story

    def test_install_cmdline(self):
        """
        Test the availability of user-defined generators from the command-line
        using `install -g`
        """
        client = TestClient()

        # Set up generator. This generator will interact with another package.
        test_generator_contents = textwrap.dedent("""
            import json
            from conans.model import Generator

            class user_defined(Generator):
                @property
                def filename(self):
                    return "userdefined.json"

                @property
                def content(self):
                    return json.dumps(list(e.ref.name for e in self.conanfile.dependencies.values()))
            """)

        # Save generator to cache_folder/generators.
        generator_path = os.path.join(client.cache.generators_path, "user_defined_generator.py")
        save(generator_path, test_generator_contents)

        client.save({"conanfile.py": GenConanfile()})
        # Test the install using a reference
        client.run("create . --name=hello --version=0.1 --user=lasote --channel=testing")
        client.run("install --reference=hello/0.1@lasote/testing -g user_defined")

        data = client.load("userdefined.json")
        json_data = json.loads(data)
        assert json_data == ['Hello']

    def test_install_conanfile(self):
        """
        Test the availability of user-defined generators from a conanfile
        """
        client = TestClient()

        # Set up generator
        test_generator_contents = textwrap.dedent("""
            from conan import ConanFile
            from conans.model import Generator

            class user_defined(Generator):
                @property
                def filename(self):
                    return "userdefined.txt"

                @property
                def content(self):
                    return "user_defined contents"
            """)
        # Save generator to cache_folder/generators.
        generator_path = os.path.join(client.cache.generators_path, "user_defined_generator.py")
        save(generator_path, test_generator_contents)

        conanfile_py = textwrap.dedent("""
            from conan import ConanFile, tools

            class HelloConan(ConanFile):
                generators = "user_defined"

                def package(self):
                    self.output.info("create_conanfile_test: {}"
                                      .format(tools.load("userdefined.txt")))
                """)
        client.save({"conanfile.py": conanfile_py})

        # Test the install using a conanfile
        client.run("install . --build")

        data = client.load("userdefined.txt")
        self.assertEqual(data, "user_defined contents")

        # Test the install using a conanfile
        client.run("create . --name=hello --version=0.1 --user=lasote --channel=testing")
        self.assertIn("Generator user_defined created userdefined.txt", client.out)
        self.assertIn("create_conanfile_test: user_defined contents", client.out)

        client.run("install --reference=hello/0.1@lasote/testing --build")
