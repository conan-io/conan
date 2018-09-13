import os
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


conanfile_basic = """
from conans import ConanFile

class AConan(ConanFile):
    name = "basic"
    version = "0.1"
"""

complete_plugin = """
def pre_export(output, conanfile, conanfile_path, reference, **kwargs):
    assert conanfile
    assert conanfile_path
    assert reference
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference)

def post_export(output, conanfile, conanfile_path, reference, **kwargs):
    assert conanfile
    assert conanfile_path
    assert reference
    output.info("conanfile_path=%s" % conanfile_path)
    output.info("reference=%s" % reference)

def pre_source(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile_path
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        assert kwargs["reference"]
        output.info("reference=%s" % kwargs["reference"])

def post_source(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile_path
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        assert kwargs["reference"]
        output.info("reference=%s" % kwargs["reference"])

def pre_build(output, conanfile, **kwargs):
    assert conanfile
    if conanfile.in_local_cache:
        assert kwargs["reference"]
        assert kwargs["package_id"]
        output.info("reference=%s" % kwargs["reference"])
        output.info("package_id=%s" % kwargs["package_id"])
    else:
        assert kwargs["conanfile_path"]
        output.info("conanfile_path=%s" % kwargs["conanfile_path"])

def post_build(output, conanfile, **kwargs):
    assert conanfile
    if conanfile.in_local_cache:
        assert kwargs["reference"]
        assert kwargs["package_id"]
        output.info("reference=%s" % kwargs["reference"])
        output.info("package_id=%s" % kwargs["package_id"])
    else:
        assert kwargs["conanfile_path"]
        output.info("conanfile_path=%s" % kwargs["conanfile_path"])

def pre_package(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile_path
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        assert kwargs["reference"]
        assert kwargs["package_id"]
        output.info("reference=%s" % kwargs["reference"])
        output.info("package_id=%s" % kwargs["package_id"])

def post_package(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile_path
    output.info("conanfile_path=%s" % conanfile_path)
    if conanfile.in_local_cache:
        assert kwargs["reference"]
        assert kwargs["package_id"]
        print("REFERENCE", kwargs["reference"])
        output.info("reference=%s" % kwargs["reference"])
        output.info("package_id=%s" % kwargs["package_id"])

def pre_upload(output, conanfile_path, reference, remote_name, **kwargs):
    output.info("COMMON: %s, %s, %s" % (conanfile_path, reference, remote_name))

def post_upload(output, conanfile_path, reference, remote_name, **kwargs):
    output.info("COMMON: %s, %s, %s" % (conanfile_path, reference, remote_name))

def pre_upload_package(output, conanfile_path, reference, package_id, remote_name, **kwargs):
    output.info("COMMON: %s, %s, %s, %s" % (conanfile_path, reference, package_id, remote_name))

def post_upload_package(output, conanfile_path, reference, package_id, remote_name, **kwargs):
    output.info("COMMON: %s, %s, %s, %s" % (conanfile_path, reference, package_id, remote_name))

def pre_download(output, reference, remote_name, **kwargs):
    output.info("COMMON: %s, %s" % (reference, remote_name))

def post_download(output, conanfile_path, reference, remote_name, **kwargs):
    output.info("COMMON: %s, %s, %s" % (conanfile_path, reference, remote_name))

def pre_download_package(output, conanfile_path, reference, package_id, remote_name, **kwargs):
    output.info("COMMON: %s, %s, %s, %s" % (conanfile_path, reference, package_id, remote_name))

def post_download_package(output, conanfile_path, reference, package_id, remote_name, **kwargs):
    output.info("COMMON: %s, %s, %s, %s" % (conanfile_path, reference, package_id, remote_name))
"""

HEADER = "[PLUGIN - complete_plugin] {method_name}():"
REFERENCE_LOCAL = "basic/0.1@PROJECT"
REFERENCE_CACHE = "basic/0.1@danimtb/testing"
PACKAGE_ID = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"

COMMON_LOCAL = " ".join([HEADER, "COMMON:", REFERENCE_LOCAL])
COMMON_CACHE = " ".join([HEADER, "COMMON:", REFERENCE_CACHE])
IN_USER_SPACE = " ".join([HEADER, "IN USER SPACE:", REFERENCE_LOCAL])
IN_LOCAL_CACHE = " ".join([HEADER, "IN LOCAL CACHE:", REFERENCE_CACHE, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"])

common_conanfile = "[PLUGIN - complete_plugin] {method_name}(): COMMON: basic/0.1@PROJECT"
common_conanfile_path = common_conanfile + ", {conanfile_path}"

common_conanfile_cache = common_conanfile.replace("@PROJECT", "@danimtb/testing")
common_conanfile_cache_path = common_conanfile_cache + ", {conanfile_path}"
common_conanfile_cache_path_ref = common_conanfile_cache_path + ", basic/0.1@danimtb/testing"

userspace_path = "[PLUGIN - complete_plugin] {method_name}(): IN USER SPACE: {conanfile_path}"
cache_ref_pkgid = "[PLUGIN - complete_plugin] {method_name}(): IN LOCAL CACHE: basic/0.1@danimtb/testing, 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"


class PluginTest(unittest.TestCase):

    def default_plugin_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_basic})
        client.run("export . danimtb/testing")
        self.assertIn("[PLUGIN - recipe_linter] pre_export(): WARN: Conanfile doesn't have 'url'",
                      client.out)
        self.assertIn("[PLUGIN - recipe_linter] pre_export(): WARN: Conanfile doesn't have "
                      "'description'", client.out)
        self.assertIn("[PLUGIN - recipe_linter] pre_export(): WARN: Conanfile doesn't have "
                      "'license'", client.out)

    def complete_plugin_test(self):
        client = TestClient()
        plugin_path = os.path.join(client.client_cache.plugins_path, "complete_plugin.py")
        client.save({plugin_path: complete_plugin, "conanfile.py": conanfile_basic})
        conanfile_path = os.path.join(client.current_folder, "conanfile.py")
        conanfile_cache_path = client.client_cache.conanfile(
            ConanFileReference("basic", "0.1", "danimtb", "testing"))
        # TODO: CHECK CONANFILE PATH PARAMETERS IN PRE AND POST
        client.run("config set general.plugins='complete_plugin'")

        client.run("source .")
        self._check_source(conanfile_path, client.out)

        client.run("install .")
        client.run("build .")
        self._check_build(conanfile_path, client.out)

        client.run("package .")
        self._check_package(conanfile_path, client.out)

        client.run("export . danimtb/testing")
        self._check_export(conanfile_path, client.out)

        client.run("export-pkg . danimtb/testing")
        self._check_export(conanfile_path, client.out)
        self._check_export_pkg(conanfile_path, conanfile_cache_path, client.out)

        client.run("remove * --force")
        client.run("export-pkg . -pf . danimtb/testing")
        self._check_export(conanfile_path, client.out)
        self._check_export_pkg(conanfile_path, conanfile_cache_path, client.out)

        client.run("remove * --force")
        client.run("create . danimtb/testing")
        self._check_export(conanfile_path, client.out)
        self._check_source(conanfile_cache_path, client.out, in_cache=True)
        self._check_build(conanfile_cache_path, client.out, in_cache=True)
        self._check_package(conanfile_cache_path, client.out, in_cache=True)
        # print(client.out)
        # client.run("upload . danimtb/testing")  # --all ?
        # client.run("download . danimtb/testing")
        # print(client.out)
        # client.run("create . danimtb/testing")
        # print(client.out)

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

    def _check_export(self, conanfile_path,  out):
        self.assertIn("[PLUGIN - complete_plugin] pre_export(): conanfile_path=%s" % conanfile_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_export(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_export(): conanfile_path=%s" % conanfile_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_export(): reference=%s" % REFERENCE_CACHE, out)

    def _check_export_pkg(self, conanfile_path, conanfile_cache_path, out):
        self.assertIn("[PLUGIN - complete_plugin] pre_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] pre_package(): package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[PLUGIN - complete_plugin] post_package(): conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[PLUGIN - complete_plugin] post_package(): reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[PLUGIN - complete_plugin] post_package(): package_id=%s" % PACKAGE_ID, out)
