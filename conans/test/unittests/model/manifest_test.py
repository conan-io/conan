import os

from conans.client.tools import environment_append
from conans.model.manifest import FileTreeManifest
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, md5, save


class TestManifest:

    def test_tree_manifest(self):
        tmp_dir = temp_folder()
        files = {"one.ext": "aalakjshdlkjahsdlkjahsdljkhsadljkhasljkdhlkjashd",
                 "path/to/two.txt": "asdas13123",
                 "two.txt": "asdasdasdasdasdasd",
                 "folder/damn.pyc": "binarythings",
                 "folder/damn.pyo": "binarythings2",
                 "pythonfile.pyc": "binarythings3"}
        for filename, content in files.items():
            save(os.path.join(tmp_dir, filename), content)

        manifest = FileTreeManifest.create(tmp_dir)

        manifest.save(tmp_dir)
        readed_manifest = FileTreeManifest.load(tmp_dir)

        assert readed_manifest.time == manifest.time
        assert readed_manifest == manifest
        # Not included the pycs or pyo
        assert set(manifest.file_sums.keys()) == {"one.ext", "path/to/two.txt", "two.txt"}

        for filepath, md5readed in manifest.file_sums.items():
            content = files[filepath]
            assert md5(content) == md5readed

    def test_already_pyc_in_manifest(self):
        tmp_dir = temp_folder()
        save(os.path.join(tmp_dir, "man.txt"), "1478122267\nconanfile.pyc: "
                                               "2bcac725a0e6843ef351f4d18cf867ec\n"
                                               "conanfile.py: 2bcac725a0e6843ef351f4d18cf867ec\n"
                                               "conanfile.pyo: 2bcac725a0e6843ef351f4d18cf867ec\n")

        read_manifest = FileTreeManifest.loads(load(os.path.join(tmp_dir, "man.txt")))
        # Not included the pycs or pyo
        assert set(read_manifest.file_sums.keys()) == {"conanfile.py"}

    def test_special_chars(self):
        tmp_dir = temp_folder()
        save(os.path.join(tmp_dir, "conanmanifest.txt"), "1478122267\nsome: file.py: 123\n")
        read_manifest = FileTreeManifest.load(tmp_dir)
        assert read_manifest.file_sums["some: file.py"] == "123"


def test_pycache_included():
    tmp_dir = temp_folder()
    files = {"__pycache__/damn.py": "binarythings",
             "pythonfile.pyc": "binarythings3"}
    for filename, content in files.items():
        save(os.path.join(tmp_dir, filename), content)

    with environment_append({"CONAN_KEEP_PYTHON_FILES": "1"}):
        manifest = FileTreeManifest.create(tmp_dir)
    manifest = repr(manifest)
    assert "pythonfile.pyc" in manifest
    assert "__pycache__/damn.py" in manifest
