import os
import stat

from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import rmdir, save


def test_rmdir_readonly_subfolder():
    """ rmdir() must be able to remove a folder that contains a read-only sub-directory.
    On Windows this fails because the sub-directory's own read-only attribute blocks its
    removal; on POSIX it fails because removing an entry from a directory requires write
    permission on that directory, unrelated to the entry's own permissions.
    https://github.com/conan-io/conan/issues/20241
    """
    folder = temp_folder()
    readonly_dir = os.path.join(folder, "readonlydir")
    save(os.path.join(readonly_dir, "inside.txt"), "content")
    os.chmod(readonly_dir, stat.S_IREAD | stat.S_IEXEC)

    rmdir(folder)
    assert not os.path.exists(folder)
