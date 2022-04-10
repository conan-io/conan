import os
import unittest


from conans.client.hook_manager import HookManager
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.tools import redirect_output
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

    def _init(self, hook_content):
        temp_dir = temp_folder()
        hook_path = os.path.join(temp_dir, "hook_my_hook.py")
        save(hook_path, hook_content)
        hook_manager = HookManager(temp_dir)
        return hook_manager

    def test_load(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            hook_manager = self._init(my_hook)
            self.assertEqual(16, len(hook_manager.hooks))  # Checks number of methods loaded

    def test_check_output(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            hook_manager = self._init(my_hook)
            methods = hook_manager.hooks.keys()
            for method in methods:
                hook_manager.execute(method)
                self.assertIn("[HOOK - hook_my_hook.py] %s(): %s()" % (method, method), output)

    def test_no_error_with_no_method(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            other_hook = """
def my_custom_function():
    pass
"""
            hook_manager = self._init(other_hook)
            hook_manager.execute("pre_source")
            self.assertEqual("", output)

    def test_exception_in_method(self):
        output = RedirectedTestOutput()
        with redirect_output(output):
            other_hook = """
from conan.errors import ConanException

def pre_build(output, **kwargs):
    raise Exception("My custom exception")
"""
            hook_manager = self._init(other_hook)
            with self.assertRaisesRegex(ConanException, "My custom exception"):
                hook_manager.execute("pre_build")
            # Check traceback output
            try:
                hook_manager.execute("pre_build")
            except ConanException as e:
                self.assertIn("[HOOK - hook_my_hook.py] pre_build(): My custom exception", str(e))
