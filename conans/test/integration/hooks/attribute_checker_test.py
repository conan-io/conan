# coding=utf-8

import os
import unittest
import tempfile
import shutil
import textwrap
from parameterized import parameterized

from conans.client.hook_manager import HookManager, attribute_checker_hook
from conans.test.utils.tools import TestBufferConanOutput, save
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.loader import ConanFileLoader, ProcessedProfile


class AttributeCheckerTest(unittest.TestCase):
    conanfile_base = textwrap.dedent("""\
        from conans import ConanFile

        class AConan(ConanFile):
            {placeholder}
        """)
    conanfile_basic = conanfile_base.format(placeholder='pass')
    conanfile_alias = conanfile_base.format(placeholder='alias = "something"')

    def run(self, *args, **kwargs):
        hooks_folder = tempfile.mkdtemp(suffix='_hooks')
        self.tmp_folder = tempfile.mkdtemp()
        try:
            output = TestBufferConanOutput()
            self.hook_manager = HookManager(hooks_folder,
                                            hook_names=["attribute_checker", ],
                                            output=output)
            super(AttributeCheckerTest, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(hooks_folder)
            shutil.rmtree(self.tmp_folder)

    @parameterized.expand([(conanfile_basic, True), (conanfile_alias, False)])
    def test_conanfile(self, conanfile_content, warn_expected):
        file_path = os.path.join(self.tmp_folder, "conanfile.py")
        save(file_path, conanfile_content)

        loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))
        conanfile = loader.load_conanfile(file_path, None, ProcessedProfile())
        self.hook_manager.execute("pre_export", conanfile=conanfile,
                                  conanfile_path=None, reference=None)

        assert_function = self.assertIn if warn_expected else self.assertNotIn
        assert_function("Conanfile doesn't have 'url'.", self.hook_manager.output)
        assert_function("Conanfile doesn't have 'license'.", self.hook_manager.output)
        assert_function("Conanfile doesn't have 'description'.", self.hook_manager.output)

