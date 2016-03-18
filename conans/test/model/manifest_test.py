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
                 "two.txt": "asdasdasdasdasdasd"}
        for filename, content in files.items():
            save(os.path.join(tmp_dir, filename), content)

        manifest = FileTreeManifest.create(tmp_dir)

        save(os.path.join(tmp_dir, "THEMANIFEST.txt"), str(manifest))

        readed_manifest = FileTreeManifest.loads(load(os.path.join(tmp_dir, "THEMANIFEST.txt")))

        self.assertEquals(readed_manifest, manifest)

        for filepath, md5readed in manifest.file_sums.items():
            content = files[filepath]
            self.assertEquals(md5(content), md5readed)
