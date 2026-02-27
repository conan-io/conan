import os
import shutil

import pytest

from conan.test.utils.tools import TestClient


class TestEncodings:

    @pytest.mark.parametrize("filename", ["conanfile_utf8.txt",
                                          "conanfile_utf8_with_bom.txt",
                                          "conanfile_utf16le_with_bom.txt",
                                          "conanfile_utf16be_with_bom.txt"])
    def test_encoding(self, filename):
        c = TestClient()
        path = os.path.join(os.path.dirname(__file__), "files", filename)
        shutil.copy(path, os.path.join(c.current_folder, "conanfile.txt"))
        c.run("install .")
        assert "Installing packages" in c.out

    def test_error(self):
        c = TestClient()
        conanfile = b"\x81\x8D\x8F\x90\x9D"
        open(os.path.join(c.current_folder, "conanfile.txt"), "wb").write(conanfile)
        c.run("install .", assert_error=True)
        assert "ERROR: Cannot load conanfile.txt" in c.out
        assert "It is recommended to use utf-8 encoding" in c.out


class TestProfileEncodings:

    def test_encoding(self):
        c = TestClient()
        c.save({"conanfile.txt": ""})
        # BOM for utf-7
        open(os.path.join(c.current_folder, "profile"), "wb").write(b'\x2b\x2f\x76\x38')
        c.run("install . -pr=profile")
        assert "Installing packages" in c.out

    def test_error(self):
        c = TestClient()
        c.save({"conanfile.txt": ""})
        open(os.path.join(c.current_folder, "profile"), "wb").write(b"\x81\x8D\x8F\x90\x9D")
        c.run("install . -pr=profile", assert_error=True)
        assert "ERROR: Cannot load profile" in c.out
        assert "It is recommended to use utf-8 encoding" in c.out
