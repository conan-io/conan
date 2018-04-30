import unittest
from conans.util.files import save, load, md5
import os
from conans.model.manifest import FileTreeManifest
from conans.test.utils.test_files import temp_folder


class ManifestTest(unittest.TestCase):

    def test_tree_manifest(self):
        tmp_dir = temp_folder()
        files = {"one.ext": "aalakjshdlkjahsdlkjahsdljkhsadljkhasljkdhlkjashd",
                 "path/to/two.txt": "asdas13123",
                 "two.txt": "asdasdasdasdasdasd",
                 "folder/damn.pyc": "binarythings",
                 "folder/damn.pyo": "binarythings2",
                 "pythonfile.pyc": "binarythings3"}
        for filename, content in files.items():
            save(os.path.join(tmp_dir, filename), content)

        manifest = FileTreeManifest.create(tmp_dir)

        manifest.save(tmp_dir)
        readed_manifest = FileTreeManifest.load(tmp_dir)

        self.assertEqual(readed_manifest.time, manifest.time)
        self.assertEqual(readed_manifest, manifest)
        # Not included the pycs or pyo
        self.assertEquals(set(manifest.file_sums.keys()),
                          set(["one.ext", "path/to/two.txt", "two.txt"]))

        for filepath, md5readed in manifest.file_sums.items():
            content = files[filepath]
            self.assertEquals(md5(content), md5readed)

    def already_pyc_in_manifest_test(self):
        tmp_dir = temp_folder()
        save(os.path.join(tmp_dir, "man.txt"), "1478122267\nconanfile.pyc: "
                                               "2bcac725a0e6843ef351f4d18cf867ec\n"
                                               "conanfile.py: 2bcac725a0e6843ef351f4d18cf867ec\n"
                                               "conanfile.pyo: 2bcac725a0e6843ef351f4d18cf867ec\n")

        read_manifest = FileTreeManifest.loads(load(os.path.join(tmp_dir, "man.txt")))
        # Not included the pycs or pyo
        self.assertEquals(set(read_manifest.file_sums.keys()),
                          set(["conanfile.py"]))
