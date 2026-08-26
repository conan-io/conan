import os
import platform
import stat

import pytest

from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import rmdir, save


@pytest.mark.skipif(platform.system() != "Windows",
                    reason="The read-only directory attribute is only relevant on Windows")
def test_rmdir_readonly_subfolder():
    """ rmdir() must be able to remove a folder that contains a read-only sub-directory
    https://github.com/conan-io/conan/issues/20241
    """
    folder = temp_folder()
    readonly_dir = os.path.join(folder, "readonlydir")
    save(os.path.join(readonly_dir, "inside.txt"), "content")
    os.chmod(readonly_dir, stat.S_IREAD | stat.S_IEXEC)

    rmdir(folder)
    assert not os.path.exists(folder)
