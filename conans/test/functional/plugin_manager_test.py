import os
import unittest

from conans import load
from conans.client.plugin_manager import PluginManager
from conans.errors import ConanException
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

    def _init(self):
        temp_dir = temp_folder()
        plugin_path = os.path.join(temp_dir, "my_plugin.py")
        save(os.path.join(temp_dir, "my_plugin.py"), my_plugin)
        output = TestBufferConanOutput()
        plugin_manager = PluginManager(temp_dir, ["my_plugin"], output)
        return plugin_manager, output, plugin_path

    def load_test(self):
        plugin_manager, output, _ = self._init()
        self.assertEqual({}, plugin_manager.plugins)
        self.assertEqual(["my_plugin"], plugin_manager._plugin_names)
        plugin_manager.load_plugins()
        self.assertEqual(16, len(plugin_manager.plugins))  # Checks number of methods loaded

    def check_output_test(self):
        plugin_manager, output, _ = self._init()
        plugin_manager.load_plugins()
        methods = plugin_manager.plugins.keys()
        for method in methods:
            plugin_manager.execute(method)
            self.assertIn("[PLUGIN - my_plugin] %s(): %s()" % (method, method), output)

    def no_error_with_no_method_test(self):
        plugin_manager, output, plugin_path = self._init()
        other_plugin = """
def my_custom_function():
    pass
"""
        save(plugin_path, other_plugin)
        self.assertEqual(other_plugin, load(plugin_path))
        plugin_manager.execute("pre_source")
        self.assertEqual("", output)

    def exception_in_method_test(self):
        plugin_manager, output, plugin_path = self._init()
        my_plugin = """
from conans.errors import ConanException

def pre_build(output, **kwargs):
    raise Exception("My custom exception")
"""
        save(plugin_path, my_plugin)
        with self.assertRaisesRegexp(ConanException, "My custom exception"):
            plugin_manager.execute("pre_build")
        # Check traceback output
        try:
            plugin_manager.execute("pre_build")
        except ConanException as e:
            self.assertIn("[PLUGIN - my_plugin] pre_build(): My custom exception", str(e))
