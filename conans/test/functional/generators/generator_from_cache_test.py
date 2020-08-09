# -*- coding: utf-8 -*-

import json
import os
import textwrap
import unittest

from conans.client.cache.cache import GENERATORS_FOLDER
from conans.test.utils.tools import TestClient


class GeneratorFromCacheTest(unittest.TestCase):
    """
    Tests user defined generators loaded from the generators folder in
    the client cache.
    """

    def install_cmdline_test(self):
        """
        Test the availability of user-defined generators from the command-line
        using `install -g`
        """
        client = TestClient(cache_autopopulate=True)

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
                return json.dumps(self.deps_env_info.vars)
        """)
        test_generator_filename = "user_defined_generator.py"

        # Save generator to cache_folder/generators.
        client.save({
            os.path.join(client.cache_folder,
                         GENERATORS_FOLDER,
                         test_generator_filename): test_generator_contents})

        conanfile_py = textwrap.dedent("""
            from conans import ConanFile

            class HelloConan(ConanFile):
                build_policy = "always"

                def package_info(self):
                    self.env_info.MY_ENV_VAR1 = "foo"
                    self.env_info.MY_ENV_VAR2 = "bar"
                    self.env_info.MY_ENV_VAR3 = "baz"
                    """)
        client.save({"conanfile.py": conanfile_py})

        # Test the install using a reference
        client.run("export . Hello/0.1@lasote/testing")
        client.run("install Hello/0.1@lasote/testing -g user_defined")

        data = client.load("userdefined.json")
        json_data = json.loads(data)
        self.assertEqual(json_data["MY_ENV_VAR1"], "foo")
        self.assertEqual(json_data["MY_ENV_VAR2"], "bar")
        self.assertEqual(json_data["MY_ENV_VAR3"], "baz")

    def install_conanfile_test(self):
        """
        Test the availability of user-defined generators from a conanfile
        """
        client = TestClient(cache_autopopulate=True)

        # Set up generator
        test_generator_contents = textwrap.dedent("""
        from conans import ConanFile
        from conans.model import Generator

        class user_defined(Generator):
            @property
            def filename(self):
                return "userdefined.txt"

            @property
            def content(self):
                return "user_defined contents"

        class UserDefinedConan(ConanFile):
            name = "User Defined Generator"
            version = "1.0"
        """)
        test_generator_filename = "user_defined_generator.py"

        # Save generator to cache_folder/generators
        client.save({
            os.path.join(client.cache_folder,
                         GENERATORS_FOLDER,
                         test_generator_filename): test_generator_contents})

        conanfile_py = textwrap.dedent("""
            from conans import ConanFile

            class HelloConan(ConanFile):
                generators = "user_defined"
                """)
        client.save({"conanfile.py": conanfile_py})

        # Test the install using a conanfile
        client.run("install . --build")

        data = client.load("userdefined.txt")
        self.assertEqual(data, "user_defined contents")
