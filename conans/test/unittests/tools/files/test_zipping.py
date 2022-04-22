import os
import zipfile
from os.path import basename

import pytest

from conan.tools.files import unzip
from conans.test.utils.mocks import MockConanfile
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


def test_impossible_to_import_untargz():
    with pytest.raises(ImportError) as exc:
        from conan.tools.files import untargz


def test_unzip():
    tmp_dir = temp_folder()
    file_path = os.path.join(tmp_dir, "foo.txt")
    save(os.path.join(tmp_dir, "foo.txt"), "bar")
    zf = zipfile.ZipFile(os.path.join(tmp_dir, 'zipfile.zip'), mode='w')
    zf.write(file_path, basename(file_path))
    zf.close()

    conanfile = MockConanfile({})

    # Unzip and check permissions are kept
    dest_dir = temp_folder()
    unzip(conanfile, os.path.join(tmp_dir, 'zipfile.zip'), dest_dir)
    assert os.path.exists(os.path.join(dest_dir, "foo.txt"))
