import os
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer

conanfile_basic = """
from conans import ConanFile

class AConan(ConanFile):
    name = "basic"
    version = "0.1"

    def package_info(self):
        self.cpp_info.defines = ["ACONAN"]
"""

complete_hook = """
import os
from conans.model.ref import ConanFileReference


def pre_export(output, conanfile, conanfile_path, reference, **kwargs):
    assert conanfile
    assert conanfile.recipe_folder == os.path.dirname(conanfile_path)
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))

def post_export(output, conanfile, conanfile_path, reference, **kwargs):
    assert conanfile
    # In this case the recipe folder is different than the final export folder
    # TODO: If export_folder will be defined it should match
    assert conanfile.recipe_folder != os.path.dirname(conanfile_path)
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))

def pre_source(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile.recipe_folder == os.path.dirname(conanfile_path)
    output.info("conanfile_path={}".format(conanfile_path))
    if conanfile.in_local_cache:
        output.info("reference={}".format(kwargs["reference"].full_str()))

def post_source(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile.recipe_folder == os.path.dirname(conanfile_path)
    output.info("conanfile_path={}".format(conanfile_path))
    if conanfile.in_local_cache:
        output.info("reference={}".format(kwargs["reference"].full_str()))

def pre_build(output, conanfile, **kwargs):
    assert conanfile
    if conanfile.in_local_cache:
        output.info("reference={}".format(kwargs["reference"].full_str()))
        output.info("package_id={}".format(kwargs["package_id"]))
    else:
        output.info("conanfile_path={}".format(kwargs["conanfile_path"]))

def post_build(output, conanfile, **kwargs):
    assert conanfile
    if conanfile.in_local_cache:
        output.info("reference={}".format(kwargs["reference"].full_str()))
        output.info("package_id={}".format(kwargs["package_id"]))
    else:
        output.info("conanfile_path={}".format(kwargs["conanfile_path"]))

def pre_package(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile.recipe_folder == os.path.dirname(conanfile_path)
    output.info("conanfile_path={}".format(conanfile_path))
    if conanfile.in_local_cache:
        output.info("reference={}".format(kwargs["reference"].full_str()))
        output.info("package_id={}".format(kwargs["package_id"]))

def post_package(output, conanfile, conanfile_path, **kwargs):
    assert conanfile
    assert conanfile.recipe_folder == os.path.dirname(conanfile_path)
    output.info("conanfile_path={}".format(conanfile_path))
    if conanfile.in_local_cache:
        output.info("reference={}".format(kwargs["reference"].full_str()))
        output.info("package_id={}".format(kwargs["package_id"]))

def pre_upload(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def post_upload(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def pre_upload_recipe(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def post_upload_recipe(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def pre_upload_package(output, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("package_id={}".format(package_id))
    output.info("remote.name={}".format(remote.name))

def post_upload_package(output, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("package_id={}".format(package_id))
    output.info("remote.name={}".format(remote.name))

def pre_download(output, reference, remote, **kwargs):
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def post_download(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def pre_download_recipe(output, reference, remote, **kwargs):
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def post_download_recipe(output, conanfile_path, reference, remote, **kwargs):
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("remote.name={}".format(remote.name))

def pre_download_package(output, conanfile, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile.name={}".format(conanfile.name))
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("package_id={}".format(package_id))
    output.info("remote.name={}".format(remote.name))

def post_download_package(output, conanfile, conanfile_path, reference, package_id, remote, **kwargs):
    output.info("conanfile.name={}".format(conanfile.name))
    output.info("conanfile_path={}".format(conanfile_path))
    output.info("reference={}".format(reference.full_str()))
    output.info("package_id={}".format(package_id))
    output.info("remote.name={}".format(remote.name))

def pre_package_info(output, conanfile, reference, **kwargs):
    output.info("reference={}".format(reference.full_str()))
    output.info("conanfile.cpp_info.defines={}".format(conanfile.cpp_info.defines))

def post_package_info(output, conanfile, reference, **kwargs):
    output.info("reference={}".format(reference.full_str()))
    output.info("conanfile.cpp_info.defines={}".format(conanfile.cpp_info.defines))
"""

HEADER = "[HOOK - complete_hook] {method_name}():"
REFERENCE_LOCAL = "basic/0.1@PROJECT"
REFERENCE_CACHE = "basic/0.1@danimtb/testing"
PACKAGE_ID = NO_SETTINGS_PACKAGE_ID

custom_module = """
def my_printer(output):
    output.info("my_printer(): CUSTOM MODULE")
"""

my_hook = """
from custom_module.custom import my_printer

def pre_export(output, conanfile_path, reference, **kwargs):
    my_printer(output)
"""


class HookTest(unittest.TestCase):

    def test_default_hook(self):
        client = TestClient()
        self.assertTrue(client.cache.hooks_path.endswith("hooks"))
        client.save({"conanfile.py": conanfile_basic})
        client.run("export . danimtb/testing")
        self.assertIn("[HOOK - attribute_checker.py] pre_export(): "
                      "WARN: Conanfile doesn't have 'url'", client.out)
        self.assertIn("[HOOK - attribute_checker.py] pre_export(): "
                      "WARN: Conanfile doesn't have 'description'", client.out)
        self.assertIn("[HOOK - attribute_checker.py] pre_export(): "
                      "WARN: Conanfile doesn't have 'license'", client.out)

    def test_complete_hook(self):
        server = TestServer([], users={"danimtb": "pass"})
        client = TestClient(servers={"default": server}, users={"default": [("danimtb", "pass")]})
        hook_path = os.path.join(client.cache.hooks_path, "complete_hook", "complete_hook.py")
        client.save({hook_path: complete_hook, "conanfile.py": conanfile_basic})
        conanfile_path = os.path.join(client.current_folder, "conanfile.py")
        conanfile_cache_path = client.cache.package_layout(
            ConanFileReference("basic", "0.1", "danimtb", "testing")).conanfile()
        client.run("config set hooks.complete_hook/complete_hook.py")

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
        client.run('export-pkg . danimtb/testing -pf . ')
        self._check_export(conanfile_path, conanfile_cache_path, client.out)
        self._check_export_pkg(conanfile_cache_path, client.out)

        client.run("remove * --force")
        client.run("create . danimtb/testing")
        self._check_export(conanfile_path, conanfile_cache_path, client.out)  # Export gets
        self._check_source(conanfile_cache_path, client.out, in_cache=True)
        self._check_build(conanfile_cache_path, client.out, in_cache=True)
        self._check_package(conanfile_cache_path, client.out, in_cache=True)
        self._check_package_info(client.out)

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
        self._check_package_info(client.out)

    def _check_source(self, conanfile_path, out, in_cache=False):
        reference = REFERENCE_CACHE if in_cache else REFERENCE_LOCAL
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_source(): "
                      "conanfile_path=%s" % conanfile_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_source(): "
                      "conanfile_path=%s" % conanfile_path, out)
        if in_cache:
            self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_source(): "
                          "reference=%s" % reference, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] post_source(): "
                          "reference=%s" % reference, out)

    def _check_build(self, conanfile_path, out, in_cache=False):
        reference = REFERENCE_CACHE if in_cache else REFERENCE_LOCAL
        if in_cache:
            self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_build(): "
                          "reference=%s" % reference, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_build(): "
                          "package_id=%s" % PACKAGE_ID, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] post_build(): "
                          "reference=%s" % reference, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] post_build(): "
                          "package_id=%s" % PACKAGE_ID, out)
        else:
            self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_build(): "
                          "conanfile_path=%s" % conanfile_path, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] post_build(): "
                          "conanfile_path=%s" % conanfile_path, out)

    def _check_package(self, conanfile_path, out, in_cache=False):
        reference = REFERENCE_CACHE if in_cache else REFERENCE_LOCAL
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package(): "
                      "conanfile_path=%s" % conanfile_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package(): "
                      "conanfile_path=%s" % conanfile_path, out)
        if in_cache:
            self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package(): "
                          "reference=%s" % reference, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package(): "
                          "package_id=%s" % PACKAGE_ID, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package(): "
                          "reference=%s" % reference, out)
            self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package(): "
                          "package_id=%s" % PACKAGE_ID, out)

    def _check_export(self, conanfile_path, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_export(): "
                      "conanfile_path=%s" % conanfile_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_export(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_export(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_export(): "
                      "reference=%s" % REFERENCE_CACHE, out)

    def _check_export_pkg(self, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package(): "
                      "package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package(): "
                      "package_id=%s" % PACKAGE_ID, out)

    def _check_upload(self, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload(): "
                      "remote.name=default", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload(): "
                      "remote.name=default", out)

    def _check_upload_recipe(self, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload_recipe(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload_recipe(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload_recipe(): "
                      "remote.name=default", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload_recipe(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload_recipe(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload_recipe(): "
                      "remote.name=default", out)

    def _check_upload_package(self, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload_package(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload_package(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload_package(): "
                      "package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_upload_package(): "
                      "remote.name=default", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload_package(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload_package(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload_package(): "
                      "package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_upload_package(): "
                      "remote.name=default", out)

    def _check_download(self, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download(): "
                      "remote.name=default", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download(): "
                      "remote.name=default", out)

    def _check_download_recipe(self, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download_recipe(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download_recipe(): "
                      "remote.name=default", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_recipe(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_recipe(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_recipe(): "
                      "remote.name=default", out)

    def _check_download_package(self, conanfile_cache_path, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download_package(): "
                      "conanfile.name=basic", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download_package(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download_package(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download_package(): "
                      "package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_download_package(): "
                      "remote.name=default", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_package(): "
                      "conanfile.name=basic", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_package(): "
                      "conanfile_path=%s" % conanfile_cache_path, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_package(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_package(): "
                      "package_id=%s" % PACKAGE_ID, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_download_package(): "
                      "remote.name=default", out)

    def _check_package_info(self, out):
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package_info(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] pre_package_info(): "
                      "conanfile.cpp_info.defines=[]", out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package_info(): "
                      "reference=%s" % REFERENCE_CACHE, out)
        self.assertIn("[HOOK - complete_hook/complete_hook.py] post_package_info(): "
                      "conanfile.cpp_info.defines=['ACONAN']", out)

    def test_import_hook(self):
        client = TestClient()
        hook_path = os.path.join(client.cache.hooks_path, "my_hook", "my_hook.py")
        init_path = os.path.join(client.cache.hooks_path, "my_hook", "custom_module", "__init__.py")
        custom_path = os.path.join(client.cache.hooks_path, "my_hook", "custom_module", "custom.py")
        client.save({init_path: "",
                     custom_path: custom_module,
                     hook_path: my_hook,
                     "conanfile.py": conanfile_basic})
        client.run("config set hooks.my_hook/my_hook.py")
        client.run("export . danimtb/testing")
        self.assertIn("[HOOK - my_hook/my_hook.py] pre_export(): my_printer(): CUSTOM MODULE",
                      client.out)
