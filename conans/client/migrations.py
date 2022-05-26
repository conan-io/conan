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
        self._update_settings_yml(cache)

    def _update_settings_yml(self, cache):
        from conans.client.conf import get_default_settings_yml
        settings_path = cache.settings_path
        out = ConanOutput()

        if not os.path.exists(settings_path):
            out.warning("Migration: This conan installation doesn't have settings yet")
            out.warning("Nothing to migrate here, settings will be generated automatically")
            return

        if not self.can_be_overwritten(settings_path):
            out.warning(f"Migration: {settings_path} does not contain the Conan"
                        f" comment: '{CONAN_GENERATED_COMMENT}'. Ignoring it")
            return
        else:
            out.warning("Migration: Updating settings.yml")
            new_settings = get_default_settings_yml()
            if new_settings == load(settings_path):
                out.info("Migration: settings.yml is already up to date")
                return
            else:
                save(cache.settings_path, new_settings)
                out.success("Migration: Successfully updated settings.yml")
