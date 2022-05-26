import os

from conans.cli.output import ConanOutput
from conans.client.cache.cache import ClientCache
from conans.migrations import Migrator, CONAN_GENERATED_COMMENT
from conans.util.files import load, save


class ClientMigrator(Migrator):

    def __init__(self, cache_folder, current_version):
        self.cache_folder = cache_folder
        super(ClientMigrator, self).__init__(cache_folder, current_version)

    def _apply_migrations(self, old_version):
        # Migrate the settings if they were the default for that version
        cache = ClientCache(self.cache_folder)
        # Time for migrations!
        self._update_settings_yml(cache)
        self._update_binary_compatibilty_files(cache)

    def _update_file(self, file_path, new_content):
        """
        Update any file path given with the new content.
        Notice that the file is only updated whether it contains the ``CONAN_GENERATED_COMMENT``.

        :param file_path: ``str`` path to the file.
        :param new_content: ``str`` content to be saved.
        """
        out = ConanOutput()
        file_name = os.path.basename(file_path)

        if not os.path.exists(file_path):
            out.warning(f"Migration: This conan installation does not have {file_name} yet")
            out.warning(f"Nothing to migrate here, {file_name} will be generated automatically")
            return

        if not self.can_be_overwritten(file_path):
            out.warning(f"Migration: {file_path} does not contain the Conan"
                        f" comment: '{CONAN_GENERATED_COMMENT}'. Ignoring it")
            return
        else:
            if new_content == load(file_path):
                return
            else:
                save(file_path, new_content)
                out.success(f"Migration: Successfully updated {file_name}")

    def _update_settings_yml(self, cache):
        """
        Update settings.yml
        """
        from conans.client.conf import get_default_settings_yml

        settings_path = cache.settings_path
        self._update_file(settings_path, get_default_settings_yml())

    def _update_binary_compatibilty_files(self, cache):
        """
        Update compatibility.py, app_compat.py, and cppstd_compat.py.
        """
        from conans.client.graph.compatibility import BinaryCompatibility, get_default_cppstd_compat,\
            get_default_app_compat, get_default_compatibility

        compatibility_file, app_compat_file, cppstd_compat_file = \
            BinaryCompatibility.get_binary_compatibility_file_paths(cache)
        self._update_file(compatibility_file, get_default_compatibility())
        self._update_file(app_compat_file, get_default_app_compat())
        self._update_file(cppstd_compat_file, get_default_cppstd_compat())
