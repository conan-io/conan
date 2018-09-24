import os
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, TestServer

conanfile_basic = """
from conans import ConanFile

class AConan(ConanFile):
    name = "basic"
    version = "0.1"
"""

complete_plugin = """
from conans.model.ref import ConanFileReference


def pre_export(output, conanfile, conanfile_path, reference, **kwargs):
    assert conanfile
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())

def post_export(output, conanfile, conanfile_path, reference, **kwargs):
    assert conanfile
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())

def pre_source(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        output.info("reference=%s" % kwargs["reference"].full_repr())

def post_source(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        output.info("reference=%s" % kwargs["reference"].full_repr())

def pre_build(output, conanfile, **kwargs):
    assert conanfile
    if conanfile.in_local_cache:
        output.info("reference=%s" % kwargs["reference"].full_repr())
        output.info("package_id=%s" % kwargs["package_id"])
    else:
        output.info("conanfile_path=%s" % kwargs["conanfile_path"])

def post_build(output, conanfile, **kwargs):
    assert conanfile
    if conanfile.in_local_cache:
        output.info("reference=%s" % kwargs["reference"].full_repr())
        output.info("package_id=%s" % kwargs["package_id"])
    else:
        output.info("conanfile_path=%s" % kwargs["conanfile_path"])

def pre_package(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        output.info("reference=%s" % kwargs["reference"].full_repr())
        output.info("package_id=%s" % kwargs["package_id"])

def post_package(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        output.info("reference=%s" % kwargs["reference"].full_repr())
        output.info("package_id=%s" % kwargs["package_id"])

def pre_upload(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def post_upload(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def pre_upload_recipe(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def post_upload_recipe(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def pre_upload_package(output, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("package_id=%s" % package_id)
    output.info("remote.name=%s" % remote.name)

def post_upload_package(output, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("package_id=%s" % package_id)
    output.info("remote.name=%s" % remote.name)

def pre_download(output, reference, remote, **kwargs):
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def post_download(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def pre_download_recipe(output, reference, remote, **kwargs):
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def post_download_recipe(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("remote.name=%s" % remote.name)

def pre_download_package(output, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("package_id=%s" % package_id)
    output.info("remote.name=%s" % remote.name)

def post_download_package(output, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference.full_repr())
    output.info("package_id=%s" % package_id)
    output.info("remote.name=%s" % remote.name)
"""

HEADER = "[PLUGIN - complete_plugin] {method_name}():"
REFERENCE_LOCAL = "basic/0.1@PROJECT"
REFERENCE_CACHE = "basic/0.1@danimtb/testing"
PACKAGE_ID = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"

custom_module = """
def my_printer(output):
    output.info("my_printer(): CUSTOM MODULE")
"""

my_plugin = """
from custom_module.custom import my_printer

def pre_export(output, conanfile_path, reference, **kwargs):
    my_printer(output)
"""


class PluginTest(unittest.TestCase):

    def default_plugin_test(self):
        client = TestClient()
        self.assertTrue(client.client_cache.plugins_path.endswith("plugins"))
        client.save({"conanfile.py": conanfile_basic})
        client.run("export . danimtb/testing")
        self.assertIn("[PLUGIN - attribute_checker] pre_export(): WARN: Conanfile doesn't have 'url'",
                      client.out)
        self.assertIn("[PLUGIN - attribute_checker] pre_export(): WARN: Conanfile doesn't have "
                      "'description'", client.out)
        self.assertIn("[PLUGIN - attribute_checker] pre_export(): WARN: Conanfile doesn't have "
                      "'license'", client.out)

    def complete_plugin_test(self):
        server = TestServer([], users={"danimtb": "pass"})
        client = TestClient(servers={"default": server}, users={"default": [("danimtb", "pass")]})
        plugin_path = os.path.join(client.client_cache.plugins_path, "complete_plugin.py")
        client.save({plugin_path: complete_plugin, "conanfile.py": conanfile_basic})
        conanfile_path = os.path.join(client.current_folder, "conanfile.py")
        conanfile_cache_path = client.client_cache.conanfile(
            ConanFileReference("basic", "0.1", "danimtb", "testing"))
        client.run("config set plugins.complete_plugin")

        client.run("source .")
        self._check_source(conanfile_path, client.out)

        client.run("install .")
        client.run("build .")
        self._check_build(conanfile_path, client.out)

        client.run("package .")
        self._check_package(conanfile_path, client.out)

        client.run("export . danimtb/testing")
        self._check_export(conanfile_path, conanfile_cache_path, client.out)

        client.run("export-pkg . danimtb/testing")
        self._check_export(conanfile_path, conanfile_cache_path, client.out)
        self._check_export_pkg(conanfile_cache_path, client.out)

        client.run("remove * --force")
        client.run("export-pkg . -pf . danimtb/testing")
        self._check_export(conanfile_path, conanfile_cache_path, client.out)
        self._check_export_pkg(conanfile_cache_path, client.out)

        client.run("remove * --force")
        client.run("create . danimtb/testing")
        self._check_export(conanfile_path, conanfile_cache_path, client.out) # Export gets
        self._check_source(conanfile_cache_path, client.out, in_cache=True)
        self._check_build(conanfile_cache_path, client.out, in_cache=True)
        self._check_package(conanfile_cache_path, client.out, in_cache=True)

        client.run("upload basic/0.1@danimtb/testing -r default")
        self._check_upload(conanfile_cache_path, client.out)
        self._check_upload_recipe(conanfile_cache_path, client.out)
        client.run("upload basic/0.1@danimtb/testing -r default --all")
        self._check_upload(conanfile_cache_path, client.out)
        self._check_upload_recipe(conanfile_cache_path, client.out)
        self._check_upload_package(conanfile_cache_path, client.out)

        client.run("remove * --force")
        client.run("download basic/0.1@danimtb/testing --recipe")
        self._check_download(conanfile_cache_path, client.out)
        self._check_download_recipe(conanfile_cache_path, client.out)
        client.run("remove * --force")
        client.run("download basic/0.1@danimtb/testing")
        self._check_download(conanfile_cache_path, client.out)
        self._check_download_recipe(conanfile_cache_path, client.out)
        self._check_download_package(conanfile_cache_path, client.out)

        client.run("remove * --force")
        client.run("install basic/0.1@danimtb/testing")
        self._check_download_recipe(conanfile_cache_path, client.out)
        self._check_download_package(conanfile_cache_path, client.out)

    def _check_source(self, conanfile_path, out, in_cache=False):
        reference = REFERENCE_CACHE if in_cache else REFERENCE_LOCAL
        self.assertIn("[PLUGIN - complete_plugin] pre_source(): conanfile_path=%s" % conanfile_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_source(): conanfile_path=%s" % conanfile_path, out)
        if in_cache:
            self.assertIn("[PLUGIN - complete_plugin] pre_source(): reference=%s" % reference, out)
            self.assertIn("[PLUGIN - complete_plugin] post_source(): reference=%s" % reference, out)

    def _check_build(self, conanfile_path,  out, in_cache=False):
        reference = REFERENCE_CACHE if in_cache else REFERENCE_LOCAL
        if in_cache:
            self.assertIn("[PLUGIN - complete_plugin] pre_build(): reference=%s" % reference, out)
            self.assertIn("[PLUGIN - complete_plugin] pre_build(): package_id=%s" % PACKAGE_ID, out)
            self.assertIn("[PLUGIN - complete_plugin] post_build(): reference=%s" % reference, out)
            self.assertIn("[PLUGIN - complete_plugin] post_build(): package_id=%s" % PACKAGE_ID, out)
        else:
            self.assertIn("[PLUGIN - complete_plugin] pre_build(): conanfile_path=%s" % conanfile_path,
                          out)
            self.assertIn("[PLUGIN - complete_plugin] post_build(): conanfile_path=%s" % conanfile_path,
                          out)

    def _check_package(self, conanfile_path, out, in_cache=False):
        reference = REFERENCE_CACHE if in_cache else REFERENCE_LOCAL
        self.assertIn("[PLUGIN - complete_plugin] pre_package(): conanfile_path=%s" % conanfile_path,
                      out)
        self.assertIn("[PLUGIN - complete_plugin] post_package(): conanfile_path=%s" % conanfile_path,
                      out)
        if in_cache:
            self.assertIn("[PLUGIN - complete_plugin] pre_package(): reference=%s" % reference, out)
            self.assertIn("[PLUGIN - complete_plugin] pre_package(): package_id=%s" % PACKAGE_ID, out)
            self.assertIn("[PLUGIN - complete_plugin] post_package(): reference=%s" % reference, out)
            self.assertIn("[PLUGIN - complete_plugin] post_package(): package_id=%s" % PACKAGE_ID, out)

    def _check_export(self, conanfile_path, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_export(): conanfile_path=%s" % conanfile_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_export(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_export(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_export(): reference=%s" % REFERENCE_CACHE, out)

    def _check_export_pkg(self, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_package(): package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[PLUGIN - complete_plugin] post_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_package(): package_id=%s" % PACKAGE_ID, out)

    def _check_upload(self, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_upload(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_upload(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_upload(): remote.name=default", out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload(): remote.name=default", out)

    def _check_upload_recipe(self, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_upload_recipe(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_upload_recipe(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_upload_recipe(): remote.name=default", out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload_recipe(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload_recipe(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload_recipe(): remote.name=default", out)

    def _check_upload_package(self, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_upload_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_upload_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_upload_package(): package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_upload_package(): remote.name=default", out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload_package(): package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[PLUGIN - complete_plugin] post_upload_package(): remote.name=default", out)

    def _check_download(self, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_download(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_download(): remote.name=default", out)
        self.assertIn("[PLUGIN - complete_plugin] post_download(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_download(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_download(): remote.name=default", out)

    def _check_download_recipe(self, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_download_recipe(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_download_recipe(): remote.name=default", out)
        self.assertIn("[PLUGIN - complete_plugin] post_download_recipe(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_download_recipe(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_download_recipe(): remote.name=default", out)

    def _check_download_package(self, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_download_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_download_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_download_package(): package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_download_package(): remote.name=default", out)
        self.assertIn("[PLUGIN - complete_plugin] post_download_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_download_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_download_package(): package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[PLUGIN - complete_plugin] post_download_package(): remote.name=default", out)

    def import_plugin_test(self):
        client = TestClient()
        plugin_path = os.path.join(client.client_cache.plugins_path, "my_plugin.py")
        init_path = os.path.join(client.client_cache.plugins_path, "custom_module", "__init__.py")
        custom_path = os.path.join(client.client_cache.plugins_path, "custom_module", "custom.py")
        client.save({plugin_path: complete_plugin,
                     init_path: "",
                     custom_path: custom_module,
                     plugin_path: my_plugin,
                     "conanfile.py": conanfile_basic})
        client.run("config set plugins.my_plugin")
        client.run("export . danimtb/testing")
        self.assertIn("[PLUGIN - my_plugin] pre_export(): my_printer(): CUSTOM MODULE", client.out)
