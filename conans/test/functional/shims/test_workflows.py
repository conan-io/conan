import os
import textwrap

from conans.client.tools import environment_append
from ._base import BaseShimsTestCase


class WorkflowsTestCase(BaseShimsTestCase):
    def setUp(self):
        self.t.save({'conanfile.py': textwrap.dedent("""
            import os
            from conans import ConanFile

            class Recipe(ConanFile):
                build_requires = 'runner1/version', 'runner2/version'
                generators = 'cmake'

                def build(self):
                    self.output.info(">>> PATH: {}".format(os.getenv('PATH')))
                    self.run("runner1")
                    self.run("runner2")
            """)})

    def test_cache_workflow(self):
        self.t.run('create . consumer/cache@ --profile:host=default --profile:build=default')

        # The .shims folder is listed in the PATH variable
        path_line = [it for it in str(self.t.out).splitlines()
                     if it.startswith('consumer/cache: >>> PATH:')][0]
        self.assertIn('build/5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9/.shims', path_line)

        # Apps run with the proper environment values
        self.assertIn(textwrap.dedent("""
            ----Running------
            > runner1
            -----------------
            library-version: version1
            library-envvar: runner1-value
            """), self.t.out)
        self.assertIn(textwrap.dedent("""
            ----Running------
            > runner2
            -----------------
            library-version: version1
            library-envvar: runner2-value
            """), self.t.out)

    def test_local_workflow(self):
        self.t.run('install . consumer/local@ --profile:host=default --profile:build=default')
        # TODO: What kind of virtualenv I can add so the PATH to the shims is added?
        with environment_append({'PATH': os.path.join(self.t.current_folder, '.shims')}):
            self.t.run_command('runner1')
            self.assertEqual(textwrap.dedent("""\
                library-version: version1
                library-envvar: runner1-value
                """), self.t.out)

            self.t.run_command('runner2')
            self.assertEqual(textwrap.dedent("""\
                library-version: version1
                library-envvar: runner2-value
                """), self.t.out)

        self.t.run('build .')

        # The .shims folder is listed in the PATH variable
        path_line = [it for it in str(self.t.out).splitlines()
                     if it.startswith('conanfile.py (consumer/local): >>> PATH:')][0]
        self.assertIn(os.path.join(self.t.current_folder, '.shims'), path_line)

        # Apps run with the proper environment values
        self.assertIn(textwrap.dedent("""
            ----Running------
            > runner1
            -----------------
            library-version: version1
            library-envvar: runner1-value
            """), self.t.out)
        self.assertIn(textwrap.dedent("""
            ----Running------
            > runner2
            -----------------
            library-version: version1
            library-envvar: runner2-value
            """), self.t.out)

    def test_editable_workflow(self):
        # TODO: Test scenario where the consumer is in editable mode
        # TODO: Test scenario where the build-requires is in editable mode
        pass
