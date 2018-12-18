import os
import platform
import shutil
import subprocess
import tempfile
import textwrap
import unittest

from conans.client.remote_manager import uncompress_file
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import EXPORT_SOURCES_TGZ_NAME
from conans.test.utils.tools import TestBufferConanOutput
from conans.test.utils.tools import TestClient, TestServer


@unittest.skipUnless(platform.system() == "Darwin", "Requires OSX")
class TgzMacosDotFilesTest(unittest.TestCase):

    def _add_macos_metadata_to_file(self, filepath):
        subprocess.call(["xattr", "-w", "name", "value", filepath])

    def _test_for_metadata_in_zip_file(self, tgz, annotated_file, dot_file_expected):
        tmp_folder = tempfile.mkdtemp()
        try:
            uncompress_file(src_path=tgz,
                            dest_folder=tmp_folder,
                            output=TestBufferConanOutput())
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
            from conans import ConanFile
            
            class Lib(ConanFile):
                name = "lib"
                version = "version"
                exports_sources = "file.txt"
                
                def package(self):
                    self.copy("file.txt")
            """)

        default_server = TestServer()
        servers = {"default": default_server}
        t = TestClient(path_with_spaces=False, servers=servers,
                       users={"default": [("lasote", "mypass")]})
        t.save(files={'conanfile.py': conanfile, 'file.txt': "content"})
        self._add_macos_metadata_to_file(os.path.join(t.current_folder, 'file.txt'))
        t.run("create . lasote/channel")

        # Check if the metadata travels through the Conan commands
        pkg_ref = PackageReference.loads(
            "lib/version@lasote/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        pkg_folder = t.client_cache.package(pkg_ref)

        # 1) When copied to the package folder, the metadata is lost
        self._test_for_metadata(pkg_folder, 'file.txt', dot_file_expected=False)

        # 2) If we add metadata to a file, it will be there
        self._add_macos_metadata_to_file(os.path.join(pkg_folder, 'file.txt'))
        self._test_for_metadata(pkg_folder, 'file.txt', dot_file_expected=True)

        # 3) In the upload process, the metadata is lost again
        ref = ConanFileReference.loads("lib/version@lasote/channel")
        export_folder = t.client_cache.export(ref)
        tgz = os.path.join(export_folder, EXPORT_SOURCES_TGZ_NAME)
        self.assertFalse(os.path.exists(tgz))
        t.run("upload lib/version@lasote/channel")
        self._test_for_metadata_in_zip_file(tgz, 'file.txt', dot_file_expected=False)
