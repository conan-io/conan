import os
import unittest

from conans.client.plugins import PluginManager
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save

my_plugin = """
from conans import ConanPlugin

class MyPlugin(ConanPlugin):

    def pre_export(self):
        self.output.info("pre_export()")

    def post_export(self):
        self.output.info("post_export()")

    def pre_source(self):
        self.output.info("pre_source()")

    def post_source(self):
        self.output.info("post_source()")

    def pre_build(self):
        self.output.info("pre_build()")

    def post_build(self):
        self.output.info("post_build()")

    def pre_package(self):
        self.output.info("pre_package()")

    def post_package(self):
        self.output.info("post_package()")

    def pre_upload(self):
        self.output.info("pre_upload()")

    def post_upload(self):
        self.output.info("post_upload()")

    def pre_install(self):
        self.output.info("pre_install()")

    def post_install(self):
        self.output.info("post_install()")

    def pre_download(self):
        self.output.info("pre_download()")

    def post_download(self):
        self.output.info("post_download()")
"""


class PluginManagerTest(unittest.TestCase):

    def setUp(self):
        temp_dir = temp_folder()
        self.file_path = os.path.join(temp_dir, "my_plugin.py")
        save(self.file_path, my_plugin)
        self.output = TestBufferConanOutput()
        self.plugin_manager = PluginManager(temp_dir, ["my_plugin"], self.output)

    def load_test(self):
        self.assertIsNone(self.plugin_manager.plugins)
        # self.assertIs(["my_plugin"], self.plugin_manager._plugin_names)
        self.assertEqual(["my_plugin"], self.plugin_manager._plugin_names)
        self.assertEqual([], self.plugin_manager.loaded_plugins)
        self.plugin_manager.load_plugins()
        self.assertEqual("MyPlugin", self.plugin_manager.loaded_plugins[0].__name__)

    def check_output_test(self):
        self.plugin_manager.load_plugins()
        methods = [method for method in self.plugin_manager.loaded_plugins[0].__dict__.keys()
                   if method.startswith("pre") or method.startswith("post")]
        for method in methods:
            self.plugin_manager.execute(method)
            self.assertIn("[PLUGIN - MyPlugin]: %s()" % method, self.output)

    def no_error_with_not_implemented_method_test(self):
        my_plugin = """
from conans import ConanPlugin

class MyPlugin(ConanPlugin):
    pass
"""
        save(self.file_path, my_plugin)
        self.plugin_manager.load_plugins()
        self.plugin_manager.execute("pre_source")
        self.assertEqual("", self.output)

    def execute_method_test(self):
        self.plugin_manager.load_plugins()
        plugin = self.plugin_manager.plugins[0]
        self.assertIsNotNone(plugin.output)
        self.plugin_manager.loaded_plugins[0].pre_export(plugin)
        self.assertIn("[PLUGIN - MyPlugin]: pre_export()", self.output)

    def test_clear_plugin_attributes(self):
        """
        Plugins may not keep old attributes between calls after a "post" method execution
        """
        my_plugin = """
from conans import ConanPlugin

class MyPlugin(ConanPlugin):

    def post_upload(self):
        self.output.info("conanfile: %s, conanfile_path: %s, reference: %s, package_id: %s, "
                         "remote_name: %s" % (self.conanfile, self.conanfile_path, self.reference,
                          self.package_id, self.remote_name))

    def pre_build(self):
        self.post_upload()
        """
        save(self.file_path, my_plugin)
        self.plugin_manager.load_plugins()
        self.plugin_manager.execute("post_upload")
        self.assertIn("[PLUGIN - MyPlugin]: conanfile: This is a conanfile, conanfile_path: "
                      "fake/conanfile/path, reference: conanfile_reference, package_id: "
                      "a_package_id, remote_name: my_remote", self.output)
        self.output = TestBufferConanOutput()
        self.plugin_manager.output = self.output
        self.plugin_manager.execute("pre_build")
        self.assertIn("[PLUGIN - MyPlugin]: conanfile: None, conanfile_path: None, reference: None,"
                      " package_id: None, remote_name: None", self.output)
        self.plugin_manager.execute("post_upload")
        self.assertIn("[PLUGIN - MyPlugin]: conanfile: None, conanfile_path: None, reference: None,"
                      " package_id: None, remote_name: None", self.output)
