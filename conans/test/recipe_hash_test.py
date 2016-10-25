import unittest
from conans.util.files import save_files
from conans.test.utils.test_files import temp_folder
from conans.client.recipe_hash import get_normalized_hash
from conans.util.sha import sha1


class RecipeHashTest(unittest.TestCase):

    def compute_hash_test(self):
        tmp_dir = temp_folder()
        save_files(tmp_dir, {"file1.txt": "Some contents\r\ncontents",
                             "file2.txt":  "More contents\r\n",
                             "subfolder/file3.txt": "more\nlines",
                             "binary": '\x80abc'})

        norm_hash = get_normalized_hash(tmp_dir)
        expected_hashes_file = sha1((sha1("\x80abc".encode("utf-8")) + "\n" +
                                    sha1("Some contents\ncontents".encode("utf-8")) + "\n" +
                                    sha1("More contents\n".encode("utf-8")) + "\n" +
                                    sha1("more\nlines".encode("utf-8"))).encode("utf-8"))
        self.assertEquals(norm_hash, expected_hashes_file)
        self.assertEquals(norm_hash, "deb6fbeed96361c0c57afa1e34ebda60b97cb6cd")

