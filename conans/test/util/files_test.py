import unittest
import os

from conans.test.utils.test_files import temp_folder
from conans.util.files import save
from time import sleep


class SaveTestCase(unittest.TestCase):

    def setUp(self):
        folder = temp_folder()
        self.filepath = os.path.join(folder, "file.txt")

        # Save some content and keep timestamp
        self.content = "my content"
        save(self.filepath, self.content)
        self.timestamp = os.path.getmtime(self.filepath)
        sleep(1)  # precission is seconds, so we need to sleep

    def only_if_modified_true_test(self):
        save(self.filepath, self.content, only_if_modified=True)
        self.assertEqual(self.timestamp, os.path.getmtime(self.filepath))

    def only_if_modified_false_test(self):
        save(self.filepath, self.content, only_if_modified=False)
        self.assertNotEqual(self.timestamp, os.path.getmtime(self.filepath))

    def modified_only_true_test(self):
        save(self.filepath, "other content", only_if_modified=True)
        self.assertNotEqual(self.timestamp, os.path.getmtime(self.filepath))

    def modified_only_false_test(self):
        save(self.filepath, "other content", only_if_modified=False)
        self.assertNotEqual(self.timestamp, os.path.getmtime(self.filepath))
