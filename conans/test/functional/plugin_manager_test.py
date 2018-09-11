import os
import unittest

from conans.client.plugins import PluginManager
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save

my_plugin = """
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


class PluginManagerTest(unittest.TestCase):

    def setUp(self):
        temp_dir = temp_folder()
        self.file_path = os.path.join(temp_dir, "my_plugin.py")
        save(self.file_path, my_plugin)
        self.output = TestBufferConanOutput()
        self.plugin_manager = PluginManager(temp_dir, ["my_plugin"], self.output)

    def load_test(self):
        self.assertEqual({}, self.plugin_manager.plugins)
        self.assertEqual(["my_plugin"], self.plugin_manager._plugin_names)
        self.plugin_manager.load_plugins()
        self.assertEqual(1, len(self.plugin_manager.plugins))

    def check_output_test(self):
        self.plugin_manager.load_plugins()
        methods = [method for method in self.plugin_manager.plugins["my_plugin"].__dict__.keys()
                   if method.startswith("pre") or method.startswith("post")]
        for method in methods:
            self.plugin_manager.execute(method)
            self.assertIn("[PLUGIN - my_plugin] %s(): %s()" % (method, method), self.output)

    def no_error_with_not_implemented_method_test(self):
        my_plugin = """
def my_custom_function():
    pass
"""
        save(self.file_path, my_plugin)
        self.plugin_manager.load_plugins()
        self.plugin_manager.execute("pre_source")
        self.assertEqual("", self.output)
