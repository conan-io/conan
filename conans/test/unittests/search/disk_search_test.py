import os
import unittest

from conans.client.cache.cache import ClientCache
from conans.client.tools import chdir
from conans.model.info import ConanInfo
from conans.model.ref import ConanFileReference
from conans.paths import (BUILD_FOLDER, CONANINFO, EXPORT_FOLDER, PACKAGES_FOLDER)
from conans.search.search import search_packages, search_recipes
from conans.test.utils.test_files import temp_folder
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import save, mkdir


class SearchTest(unittest.TestCase):

    def setUp(self):
        folder = temp_folder()
        self.cache = ClientCache(folder, output=TestBufferConanOutput())
        mkdir(self.cache.store)

    def test_basic_2(self):
        with chdir(self.cache.store):
            ref1 = ConanFileReference.loads("opencv/2.4.10@lasote/testing")
            root_folder = str(ref1).replace("@", "/")
            artifacts = ["a", "b", "c"]
            reg1 = "%s/%s" % (root_folder, EXPORT_FOLDER)
            os.makedirs(reg1)
            for artif_id in artifacts:
                build1 = "%s/%s/%s" % (root_folder, BUILD_FOLDER, artif_id)
                artif1 = "%s/%s/%s" % (root_folder, PACKAGES_FOLDER, artif_id)
                os.makedirs(build1)
                info = ConanInfo().loads("[settings]\n[options]")
                save(os.path.join(artif1, CONANINFO), info.dumps())

            packages = search_packages(self.cache.package_layout(ref1), "")
            all_artif = [_artif for _artif in sorted(packages)]
            self.assertEqual(all_artif, artifacts)

    def test_pattern(self):
        with chdir(self.cache.store):
            references = ["opencv/2.4.%s@lasote/testing" % ref for ref in ("1", "2", "3")]
            refs = [ConanFileReference.loads(reference) for reference in references]
            for ref in refs:
                root_folder = str(ref).replace("@", "/")
                reg1 = "%s/%s" % (root_folder, EXPORT_FOLDER)
                os.makedirs(reg1)

            recipes = search_recipes(self.cache, "opencv/*@lasote/testing")
            self.assertEqual(recipes, refs)

    def test_case_insensitive(self):
        with chdir(self.cache.store):
            root_folder2 = "sdl/1.5/lasote/stable"
            ref2 = ConanFileReference.loads("sdl/1.5@lasote/stable")
            os.makedirs("%s/%s" % (root_folder2, EXPORT_FOLDER))

            root_folder3 = "assimp/0.14/phil/testing"
            ref3 = ConanFileReference.loads("assimp/0.14@phil/testing")
            os.makedirs("%s/%s" % (root_folder3, EXPORT_FOLDER))

            root_folder4 = "sdl/2.10/lasote/stable"
            ref4 = ConanFileReference.loads("sdl/2.10@lasote/stable")
            os.makedirs("%s/%s" % (root_folder4, EXPORT_FOLDER))

            root_folder5 = "SDL_fake/1.10/lasote/testing"
            ref5 = ConanFileReference.loads("SDL_fake/1.10@lasote/testing")
            os.makedirs("%s/%s" % (root_folder5, EXPORT_FOLDER))
            # Case insensitive searches

            reg_conans = sorted([str(_reg) for _reg in search_recipes(self.cache, "*")])
            self.assertEqual(reg_conans, [str(ref5),
                                          str(ref3),
                                          str(ref2),
                                          str(ref4)])

            reg_conans = sorted([str(_reg) for _reg in search_recipes(self.cache,
                                                                      pattern="sdl*")])
            self.assertEqual(reg_conans, [str(ref5), str(ref2), str(ref4)])

            # Case sensitive search
            self.assertEqual(str(search_recipes(self.cache, pattern="SDL*",
                                                ignorecase=False)[0]),
                             str(ref5))
