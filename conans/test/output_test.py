import unittest
from conans.client.output import ConanOutput
from six import StringIO
from conans.client.rest.uploader_downloader import print_progress
from conans.test.utils.test_files import temp_folder
from conans import tools
import zipfile
import os
from conans.util.files import save, load
import sys


class OutputTest(unittest.TestCase):

    def simple_output_test(self):
        stream = StringIO()
        output = ConanOutput(stream)
        output.rewrite_line("This is a very long line that has to be truncated somewhere, "
                            "because it is so long it doesn't fit in the output terminal")
        self.assertIn("This is a very long line that ha ... esn't fit in the output terminal",
                      stream.getvalue())

    def print_progress_test(self):
        stream = StringIO()
        output = ConanOutput(stream)
        for units in range(50):
            print_progress(output, units)
        output_str = stream.getvalue()
        self.assertNotIn("=", output_str)
        self.assertNotIn("[", output_str)
        self.assertNotIn("]", output_str)

    def unzip_output_test(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "example.txt")
        save(file_path, "Hello world!")

        zip_path = os.path.join(tmp_dir, 'example.zip')
        zipf = zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED)
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                zipf.write(os.path.join(root, f), f)
        zipf.close()

        output_dir = os.path.join(tmp_dir, "output_dir")
        new_out = StringIO()
        old_out = sys.stdout
        try:
            sys.stdout = new_out
            tools.unzip(zip_path, output_dir)
        finally:
            sys.stdout = old_out

        output = new_out.getvalue()
        self.assertRegexpMatches(output, "Unzipping [\d]+ bytes, this can take a while")
        content = load(os.path.join(output_dir, "example.txt"))
        self.assertEqual(content, "Hello world!")
