import copy
import os
import unittest

from conans.errors import NotFoundException
from conans.model.manifest import FileTreeManifest
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import CONANINFO, CONAN_MANIFEST
from conans.server.service.authorize import BasicAuthorizer
from conans.server.service.v2.search import SearchService
from conans.server.service.v2.service_v2 import ConanServiceV2
from conans.server.store.disk_adapter import ServerDiskAdapter
from conans.server.store.server_store import ServerStore
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conans.util.files import save, save_files


class MockFileSaver(object):

    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    def save(self, abspath):
        save(os.path.join(abspath, self.filename), self.content)


DEFAULT_REVISION = "1234"


class ConanServiceTest(unittest.TestCase):

    def setUp(self):
        self.ref = RecipeReference.loads("openssl/2.0.3@lasote/testing#%s" % DEFAULT_REVISION)

        self.pref = PkgReference(self.ref, "123123123", DEFAULT_REVISION)
        self.tmp_dir = temp_folder()

        read_perms = [("*/*@*/*", "*")]
        write_perms = []
        authorizer = BasicAuthorizer(read_perms, write_perms)

        self.fake_url = "http://url"
        adapter = ServerDiskAdapter(self.fake_url, self.tmp_dir)
        self.server_store = ServerStore(storage_adapter=adapter)
        self.service = ConanServiceV2(authorizer, self.server_store)
        self.search_service = SearchService(authorizer, self.server_store, "lasote")

        files = {"conanfile.py": str(GenConanfile("test"))}
        save_files(self.server_store.export(self.ref), files)
        self.server_store.update_last_revision(self.ref)
        manifest = FileTreeManifest.create(self.server_store.export(self.ref))
        conan_digest_path = os.path.join(self.server_store.export(self.ref), CONAN_MANIFEST)
        save(conan_digest_path, repr(manifest))

        files = {"boost.lib": "", "boost2.lib": ""}
        save_files(self.server_store.package(self.pref), files)

    def test_search(self):
        """ check the dict is returned by get_packages_info service
        """
        # Creating and saving conans, packages, and conans.vars
        ref2 = RecipeReference("openssl", "3.0", "lasote", "stable", DEFAULT_REVISION)
        ref3 = RecipeReference("Assimp", "1.10", "fenix", "stable", DEFAULT_REVISION)
        ref4 = RecipeReference("assimpFake", "0.1", "phil", "stable", DEFAULT_REVISION)

        pref2 = PkgReference(ref2, "12345587754", DEFAULT_REVISION)
        pref3 = PkgReference(ref3, "77777777777", DEFAULT_REVISION)

        conan_vars = """
[options]
    use_Qt=%s
"""
        conan_vars1 = conan_vars % "True"
        conan_vars2 = conan_vars % "False"
        conan_vars3 = conan_vars % "True"

        save_files(self.server_store.package(self.pref), {CONANINFO: conan_vars1})
        self.server_store.update_last_package_revision(self.pref)
        save_files(self.server_store.package(pref2), {CONANINFO: conan_vars2})
        self.server_store.update_last_package_revision(pref2)
        save_files(self.server_store.package(pref3), {CONANINFO: conan_vars3})
        self.server_store.update_last_package_revision(pref3)

        save_files(self.server_store.export(ref4), {"dummy.txt": "//"})

        info = self.search_service.search()
        expected = [RecipeReference(r.name, r.version, r.user, r.channel, revision=None)
                    for r in [ref3, ref4, self.ref, ref2]]
        self.assertEqual(expected, info)

        info = self.search_service.search(pattern="Assimp*", ignorecase=False)
        ref3_norev = copy.copy(ref3)
        ref3_norev.revision = None
        self.assertEqual(info, [ref3_norev])

        info = self.search_service.search_packages(ref2)
        self.assertEqual(info, {'12345587754': {'content': '\n[options]\n    use_Qt=False\n',
                                                }})

        info = self.search_service.search_packages(ref3)
        self.assertEqual(info, {'77777777777': {'content': '\n[options]\n    use_Qt=True\n'}
                                })

    def test_remove(self):
        ref2 = RecipeReference("OpenCV", "3.0", "lasote", "stable", DEFAULT_REVISION)
        ref3 = RecipeReference("Assimp", "1.10", "lasote", "stable", DEFAULT_REVISION)

        pref2 = PkgReference(ref2, "12345587754", DEFAULT_REVISION)
        pref3 = PkgReference(ref3, "77777777777", DEFAULT_REVISION)

        save_files(self.server_store.export(ref2), {"fake.txt": "//fake"})
        self.server_store.update_last_revision(ref2)
        save_files(self.server_store.package(pref2), {"fake.txt": "//fake"})
        self.server_store.update_last_package_revision(pref2)
        save_files(self.server_store.package(pref3), {"fake.txt": "//fake"})
        self.server_store.update_last_package_revision(pref3)

        # Delete all the conans folder
        self.service.remove_recipe(self.ref, "lasote")
        conan_path = self.server_store.base_folder(self.ref)
        self.assertFalse(os.path.exists(conan_path))

        # Raise an exception
        self.assertRaises(NotFoundException,
                          self.service.remove_recipe,
                          RecipeReference("Fake", "1.0", "lasote", "stable"), "lasote")
