import os
import unittest
from conans.paths import (BUILD_FOLDER, PACKAGES_FOLDER, EXPORT_FOLDER, SimplePaths, CONANINFO)
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
from conans.util.files import save
from conans.model.info import ConanInfo
from conans.search.search import search_recipes, search_packages


class SearchTest(unittest.TestCase):

    def setUp(self):
        folder = temp_folder()
        paths = SimplePaths(folder)
        os.chdir(paths.store)
        self.paths = paths

    def basic_test2(self):
        conan_ref1 = ConanFileReference.loads("opencv/2.4.10@lasote/testing")
        root_folder = str(conan_ref1).replace("@", "/")
        artifacts = ["a", "b", "c"]
        reg1 = "%s/%s" % (root_folder, EXPORT_FOLDER)
        os.makedirs(reg1)
        for artif_id in artifacts:
            build1 = "%s/%s/%s" % (root_folder, BUILD_FOLDER, artif_id)
            artif1 = "%s/%s/%s" % (root_folder, PACKAGES_FOLDER, artif_id)
            os.makedirs(build1)
            info = ConanInfo().loads("[settings]\n[options]")
            save(os.path.join(artif1, CONANINFO), info.dumps())

        packages = search_packages(self.paths, conan_ref1, "")
        all_artif = [_artif for _artif in sorted(packages)]
        self.assertEqual(all_artif, artifacts)

    def pattern_test(self):
        refs = ["opencv/2.4.%s@lasote/testing" % ref for ref in ("1", "2", "3")]
        refs = [ConanFileReference.loads(ref) for ref in refs]
        for ref in refs:
            root_folder = str(ref).replace("@", "/")
            reg1 = "%s/%s" % (root_folder, EXPORT_FOLDER)
            os.makedirs(reg1)

        recipes = search_recipes(self.paths, "opencv/*@lasote/testing")
        self.assertEqual(recipes, refs)

    def case_insensitive_test(self):
        root_folder2 = "sdl/1.5/lasote/stable"
        conan_ref2 = ConanFileReference.loads("sdl/1.5@lasote/stable")
        os.makedirs("%s/%s" % (root_folder2, EXPORT_FOLDER))

        root_folder3 = "assimp/0.14/phil/testing"
        conan_ref3 = ConanFileReference.loads("assimp/0.14@phil/testing")
        os.makedirs("%s/%s" % (root_folder3, EXPORT_FOLDER))

        root_folder4 = "sdl/2.10/lasote/stable"
        conan_ref4 = ConanFileReference.loads("sdl/2.10@lasote/stable")
        os.makedirs("%s/%s" % (root_folder4, EXPORT_FOLDER))

        root_folder5 = "SDL_fake/1.10/lasote/testing"
        conan_ref5 = ConanFileReference.loads("SDL_fake/1.10@lasote/testing")
        os.makedirs("%s/%s" % (root_folder5, EXPORT_FOLDER))
        # Case insensitive searches

        reg_conans = sorted([str(_reg) for _reg in search_recipes(self.paths, "*")])
        self.assertEqual(reg_conans, [str(conan_ref5),
                                      str(conan_ref3),
                                      str(conan_ref2),
                                      str(conan_ref4)])

        reg_conans = sorted([str(_reg) for _reg in search_recipes(self.paths, pattern="sdl*")])
        self.assertEqual(reg_conans, [str(conan_ref5), str(conan_ref2), str(conan_ref4)])

        # Case sensitive search
        self.assertEqual(str(search_recipes(self.paths, pattern="SDL*", ignorecase=False)[0]),
                         str(conan_ref5))
