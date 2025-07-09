import os
import stat
import pytest

from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import remove, save


class TestRemove:

    @pytest.fixture
    def setup_file(self):
        file = os.path.join(temp_folder(), 'file.txt')
        save(file, "some content")
        return file

    def test_remove(self, setup_file):
        remove(setup_file)
        assert not os.path.exists(setup_file)
        assert os.path.exists(os.path.dirname(setup_file))

    def test_remove_readonly(self, setup_file):
        os.chmod(setup_file, stat.S_IREAD|stat.S_IRGRP|stat.S_IROTH)
        with pytest.raises((IOError, OSError)):
            save(setup_file, "change the content")
        remove(setup_file)
        assert not os.path.exists(setup_file)
        assert os.path.exists(os.path.dirname(setup_file))

    def test_remove_folder(self, setup_file):
        dirname = os.path.dirname(setup_file)
        with pytest.raises(AssertionError):
            remove(dirname)
        assert os.path.exists(dirname)
