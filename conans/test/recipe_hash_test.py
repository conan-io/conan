import unittest
from conans.util.files import save_files
from conans.test.utils.test_files import temp_folder
from conans.client.recipe_hash import get_normalized_hash
from conans.util.sha import sha1


class RecipeHashTest(unittest.TestCase):

    def compute_hash_test(self):
        tmp_dir = temp_folder()
        save_files(tmp_dir, {"file1.txt": u"Some contents\r\ncontents".encode("utf-8"),
                             "file2.txt":  u"More contents\r\n".encode("utf-8"),
                             "subfolder/file3.txt": u"more\nlines".encode("utf-8"),
                             "binary": u'\x80abc'.encode("utf-8")})

        norm_hash = get_normalized_hash(tmp_dir)
        expected_hashes_file = (sha1(u"\x80abc".encode("utf-8")) + "\n" +
                                sha1(u"Some contents\ncontents".encode("utf-8")) + "\n" +
                                sha1(u"More contents\n".encode("utf-8")) + "\n" +
                                sha1(u"more\nlines".encode("utf-8")))

        expected_hashes_file = sha1(expected_hashes_file.encode("utf-8"))

        self.assertEquals(norm_hash, expected_hashes_file)
        self.assertEquals(norm_hash, "8f0e553955497e16da19411e1e8d0ece47b60793")
