import os
import pytest

from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import set_dirty, clean_dirty, set_dirty_context_manager, _DIRTY_FOLDER


class TestDirty:

    @pytest.fixture
    def setup_dirty(self):
        """ Create temporary folder to save dirty state
        """
        tempfolder = temp_folder()
        dirty_folder = tempfolder + _DIRTY_FOLDER
        return tempfolder, dirty_folder

    def test_set_dirty(self, setup_dirty):
        """ Dirty flag must be created by set_dirty
        """
        folder, dirty_folder = setup_dirty
        set_dirty(folder)
        assert os.path.exists(dirty_folder)

    def test_clean_dirty(self, setup_dirty):
        """ Dirty flag must be cleaned by clean_dirty
        """
        folder, dirty_folder = setup_dirty
        set_dirty(folder)
        assert os.path.exists(dirty_folder)
        clean_dirty(folder)
        assert not os.path.exists(dirty_folder)

    def test_set_dirty_context(self, setup_dirty):
        """ Dirty context must remove lock before exiting
        """
        folder, dirty_folder = setup_dirty
        with set_dirty_context_manager(folder):
            assert os.path.exists(dirty_folder)
        assert not os.path.exists(dirty_folder)

    def test_interrupted_dirty_context(self, setup_dirty):
        """ Broken context must preserve dirty state

            Raise an exception in middle of context. By default,
            dirty file is not removed.
        """
        folder, dirty_folder = setup_dirty
        try:
            with set_dirty_context_manager(folder):
                assert os.path.exists(dirty_folder)
                raise RuntimeError()
        except RuntimeError:
            pass
        assert os.path.exists(dirty_folder)
