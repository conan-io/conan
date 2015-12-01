import unittest
from conans.paths import BUILD_FOLDER, PACKAGES_FOLDER, EXPORT_FOLDER, StorePaths
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.server.store.disk_adapter import DiskAdapter
from conans.server.store.file_manager import FileManager
from conans.test.utils.test_files import temp_folder


class PathsTest(unittest.TestCase):

    def basic_test(self):
        folder = temp_folder()
        paths = StorePaths(folder)
        self.assertEqual(paths.store, folder)
        conan_ref = ConanFileReference.loads("opencv/2.4.10 @ lasote /testing")
        package_ref = PackageReference(conan_ref, "456fa678eae68")
        expected_base = os.path.join(paths.store, os.path.sep.join(["opencv", "2.4.10",
                                                           "lasote", "testing"]))
        self.assertEqual(paths.conan(conan_ref),
                         os.path.join(paths.store, expected_base))
        self.assertEqual(paths.export(conan_ref),
                         os.path.join(paths.store, expected_base, EXPORT_FOLDER))
        self.assertEqual(paths.build(package_ref),
                         os.path.join(paths.store, expected_base, BUILD_FOLDER,  "456fa678eae68"))
        self.assertEqual(paths.package(package_ref),
                         os.path.join(paths.store, expected_base, PACKAGES_FOLDER,  "456fa678eae68"))

    def basic_test2(self):
        # FIXME, for searches now uses file_service, not paths. So maybe move test to another place
        folder = temp_folder()
        paths = StorePaths(folder)

        os.chdir(paths.store)

        root_folder1 = "opencv/2.4.10/lasote/testing"
        conan_ref1 = ConanFileReference.loads("opencv/2.4.10@lasote/testing")

        artif_id1 = "awqfwf44we5f425fw"
        artif_id2 = "b5wc4q5frg45rgv1g"
        artif_id3 = "cf838regrg783g453"

        reg1 = "%s/%s" % (root_folder1, EXPORT_FOLDER)
        build1 = "%s/%s/%s" % (root_folder1, BUILD_FOLDER, artif_id1)
        artif1 = "%s/%s/%s" % (root_folder1, PACKAGES_FOLDER, artif_id1)
        artif2 = "%s/%s/%s" % (root_folder1, PACKAGES_FOLDER, artif_id2)
        artif3 = "%s/%s/%s" % (root_folder1, PACKAGES_FOLDER, artif_id3)
        os.makedirs(reg1)
        os.makedirs(build1)
        os.makedirs(artif1)
        os.makedirs(artif2)
        os.makedirs(artif3)

        all_artif = [_artif for _artif in sorted(paths.conan_packages(conan_ref1))]
        self.assertEqual(all_artif, [artif_id1, artif_id2, artif_id3])

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
        disk_adapter = DiskAdapter("", paths.store, None)
        file_manager = FileManager(paths, disk_adapter)

        reg_conans = sorted([str(_reg) for _reg in file_manager._exported_conans()])
        self.assertEqual(reg_conans, [str(conan_ref5),
                                      str(conan_ref3),
                                      str(conan_ref1),
                                      str(conan_ref2),
                                      str(conan_ref4)])

        reg_conans = sorted([str(_reg) for _reg in file_manager._exported_conans(pattern="sdl*")])
        self.assertEqual(reg_conans, [str(conan_ref5), str(conan_ref2), str(conan_ref4)])

        # Case sensitive search
        self.assertEqual(str(file_manager._exported_conans(pattern="SDL*", ignorecase=False)[0]),
                         str(conan_ref5))
