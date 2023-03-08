import os
import tarfile
import unittest
from unittest import TestCase

import six
from six import StringIO
import pytest

from conans import DEFAULT_REVISION_V1
from conans.client.output import ConanOutput
from conans.client.tools.files import save, unzip
from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import load, save_files


class XZTest(TestCase):
    output = TestBufferConanOutput()

    @pytest.mark.skipif(not six.PY3, reason="only Py3")
    def test(self):
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "a_file.txt")
        save(file_path, "my content!")
        txz = os.path.join(tmp_dir, "sample.tar.xz")
        with tarfile.open(txz, "w:xz") as tar:
            tar.add(file_path, "a_file.txt")

        dest_folder = temp_folder()
        unzip(txz, dest_folder, output=ConanOutput(StringIO()))
        content = load(os.path.join(dest_folder, "a_file.txt"))
        self.assertEqual(content, "my content!")

    @pytest.mark.skipif(not six.PY2, reason="only Py2")
    def test_error_python2(self):
        with six.assertRaisesRegex(self, ConanException, "XZ format not supported in Python 2"):
            dest_folder = temp_folder()
            unzip("somefile.tar.xz", dest_folder, output=self.output)
