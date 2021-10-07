import os
import unittest

import six
import pytest

from conans import load
from conans.client.hook_manager import HookManager
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import save

my_hook = """
def pre_export(output, **kwargs):
    output.info("pre_export()")

def post_export(output, **kwargs):
    output.info("post_export()")

def pre_source(output, **kwargs):
    output.info("pre_source()")

def post_source(output, **kwargs):
    output.info("post_source()")

def pre_build(output, **kwargs):
    output.info("pre_build()")

def post_build(output, **kwargs):
    output.info("post_build()")

def pre_package(output, **kwargs):
    output.info("pre_package()")

def post_package(output, **kwargs):
    output.info("post_package()")

def pre_upload(output, **kwargs):
    output.info("pre_upload()")

def post_upload(output, **kwargs):
    output.info("post_upload()")

def pre_upload_package(output, **kwargs):
    output.info("pre_upload_package()")

def post_upload_package(output, **kwargs):
    output.info("post_upload_package()")

def pre_download(output, **kwargs):
    output.info("pre_download()")

def post_download(output, **kwargs):
    output.info("post_download()")

def pre_download_package(output, **kwargs):
    output.info("pre_download_package()")

def post_download_package(output, **kwargs):
    output.info("post_download_package()")
"""


class HookManagerTest(unittest.TestCase):

    def _init(self):
        temp_dir = temp_folder()
        hook_path = os.path.join(temp_dir, "my_hook.py")
        save(os.path.join(temp_dir, "my_hook.py"), my_hook)
        output = TestBufferConanOutput()
        hook_manager = HookManager(temp_dir, ["my_hook"], output)
        return hook_manager, output, hook_path

    def test_load(self):
        hook_manager, output, _ = self._init()
        self.assertEqual({}, hook_manager.hooks)
        self.assertEqual(["my_hook"], hook_manager._hook_names)
        hook_manager.load_hooks()
        self.assertEqual(16, len(hook_manager.hooks))  # Checks number of methods loaded

    def test_check_output(self):
        hook_manager, output, _ = self._init()
        hook_manager.load_hooks()
        methods = hook_manager.hooks.keys()
        for method in methods:
            hook_manager.execute(method)
            self.assertIn("[HOOK - my_hook.py] %s(): %s()" % (method, method), output)

    @pytest.mark.skipif(six.PY2, reason="Does not pass on Py2 with Pytest")
    def test_no_error_with_no_method(self):
        hook_manager, output, hook_path = self._init()
        other_hook = """
def my_custom_function():
    pass
"""
        save(hook_path, other_hook)
        self.assertEqual(other_hook, load(hook_path))
        hook_manager.execute("pre_source")
        self.assertEqual("", output)

    @pytest.mark.skipif(six.PY2, reason="Does not pass on Py2 with Pytest")
    def test_exception_in_method(self):
        hook_manager, output, hook_path = self._init()
        my_hook = """
from conans.errors import ConanException

def pre_build(output, **kwargs):
    raise Exception("My custom exception")
"""
        save(hook_path, my_hook)
        with six.assertRaisesRegex(self, ConanException, "My custom exception"):
            hook_manager.execute("pre_build")
        # Check traceback output
        try:
            hook_manager.execute("pre_build")
        except ConanException as e:
            self.assertIn("[HOOK - my_hook.py] pre_build(): My custom exception", str(e))
