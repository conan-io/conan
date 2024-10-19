import os
import platform
import shutil
import subprocess
import tempfile
import textwrap
import unittest

import pytest

from conans.client.remote_manager import uncompress_file
from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import EXPORT_SOURCES_TGZ_NAME
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires OSX")
class TgzMacosDotFilesTest(unittest.TestCase):

    def _test_for_metadata_in_zip_file(self, tgz, annotated_file, dot_file_expected):
        tmp_folder = tempfile.mkdtemp()
        try:
            uncompress_file(src_path=tgz, dest_folder=tmp_folder)
            self.assertTrue(os.path.exists(os.path.join(tmp_folder, annotated_file)))
            self.assertEqual(dot_file_expected,
                             os.path.exists(os.path.join(tmp_folder, "._" + annotated_file)))
        finally:
            shutil.rmtree(tmp_folder)

    def _test_for_metadata(self, folder, annotated_file, dot_file_expected):
        """ We want to check if the file has metadata associated: Mac creates the
            ._ files at the moment of creating a tar file in order to send the
            metadata associated to every file. """
        self.assertTrue(os.path.exists(os.path.join(folder, annotated_file)))

        tmp_folder = tempfile.mkdtemp()
        try:
            tgz = os.path.join(tmp_folder, 'compressed.tgz')
            subprocess.call(["tar", "-zcvf", tgz, "-C", folder, "."])
            self._test_for_metadata_in_zip_file(tgz, annotated_file, dot_file_expected)
        finally:
            shutil.rmtree(tmp_folder)

    def test_dot_files(self):
        """ Check behavior related to ._ files in Macos OS

            Macos has the ability to store metadata associated to files. This metadata can be
            stored in the HFS+ (Apple native) or Unix/UFS volumes, but if the store does
            not have this capability it will be placed in a ._ file. So these files will
            automatically be created by the OS when it is creating a package in order to
            send this information.

            Nevertheless, Conan is using the Python libraries to copy, tar and untar files
            and this metadata is lost when using them. It can avoid some problems like
            #3529 but there is missing information that can be valuable at some point in time.

            This test is here just to be sure that the behavior is not changed without
            noticing.
            """

        conanfile = textwrap.dedent("""\
            from conan import ConanFile
            from conan.tools.files import copy

            class Lib(ConanFile):
                name = "lib"
                version = "version"
                exports_sources = "file.txt"

                def package(self):
                    copy(self, "file.txt", self.source_folder, self.package_folder)
            """)

        t = TestClient(path_with_spaces=False, default_server_user=True)
        t.save({'conanfile.py': conanfile, 'file.txt': "content"})

        def _add_macos_metadata_to_file(filepath):
            subprocess.call(["xattr", "-w", "name", "value", filepath])

        _add_macos_metadata_to_file(os.path.join(t.current_folder, 'file.txt'))
        t.run("create . --user=user --channel=channel")

        # Check if the metadata travels through the Conan commands
        pref = t.get_latest_package_reference(RecipeReference.loads("lib/version@user/channel"),
                                              NO_SETTINGS_PACKAGE_ID)
        pkg_folder = t.get_latest_pkg_layout(pref).package()

        # 1) When copied to the package folder, the metadata is lost
        self._test_for_metadata(pkg_folder, 'file.txt', dot_file_expected=False)

        # 2) If we add metadata to a file, it will be there
        _add_macos_metadata_to_file(os.path.join(pkg_folder, 'file.txt'))
        self._test_for_metadata(pkg_folder, 'file.txt', dot_file_expected=True)

        # 3) In the upload process, the metadata is lost again
        export_download_folder = t.get_latest_ref_layout(pref.ref).download_export()
        tgz = os.path.join(export_download_folder, EXPORT_SOURCES_TGZ_NAME)
        self.assertFalse(os.path.exists(tgz))
        t.run("upload lib/version@user/channel -r default --only-recipe")
        self._test_for_metadata_in_zip_file(tgz, 'file.txt', dot_file_expected=False)
