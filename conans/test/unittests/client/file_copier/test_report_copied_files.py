# coding=utf-8

import unittest

from conans.client.file_copier import report_copied_files
from conans.test.utils.mocks import TestBufferConanOutput


class ReportCopiedFilesTestCase(unittest.TestCase):

    def test_output_string(self):
        output = TestBufferConanOutput()

        files = ['/abs/path/to/file.pdf',
                 '../rel/path/to/file2.pdf',
                 '../rel/path/to/file3.pdf',
                 '../rel/path/to/file4.pdf',
                 '../rel/path/to/file5.pdf',
                 '../rel/path/to/file6.pdf',
                 '../rel/path/to/file7.pdf',
                 '/without/ext/no_ext1',
                 'no_ext2',
                 'a/other.txt']

        report_copied_files(files, output)
        lines = sorted(str(output).splitlines())
        self.assertEqual("Copied 7 '.pdf' files", lines[2])
        self.assertEqual("Copied 2 files: no_ext1, no_ext2", lines[1])
        self.assertEqual("Copied 1 '.txt' file: other.txt", lines[0])
