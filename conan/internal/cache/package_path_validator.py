import os
import json
from conan.api.output import ConanOutput


class PackagePathValidator:
    """
    Validates package path structure configuration and warns when it changes.
    This ensures users know they need to clear their cache when changing path structure.
    """
    
    CONFIG_FILE = "package_path_config.json"
    
    def __init__(self, cache_folder):
        self.cache_folder = cache_folder
        self.config_file_path = os.path.join(cache_folder, self.CONFIG_FILE)
    
    def validate_path_config(self, current_template):
        """
        Validates if the package path template configuration has changed since last use.
        If it has changed, warns the user to clear their cache.
        
        Args:
            current_template: The current package path template from configuration
            
        Returns:
            bool: True if configuration is valid to use, False otherwise.
        """
        # Check if we have a stored config
        previous_template = self._get_stored_template()
        
        # Store current config for future comparisons
        self._store_current_template(current_template)
        
        # If the template has changed, warn user
        if previous_template is not None and previous_template != current_template:
            ConanOutput().warning(
                f"Package path template configuration has changed from '{previous_template}' to "
                f"'{current_template}'. This affects where packages are stored in the cache."
            )
            ConanOutput().warning(
                "For the change to take effect properly, you should remove the existing cache by running: "
                "conan cache clean --output"
            )
            return False
        
        return True
    
    def _get_stored_template(self):
        """Gets the stored template from the config file"""
        if not os.path.exists(self.config_file_path):
            return None
            
        try:
            with open(self.config_file_path, 'r') as f:
                data = json.load(f)
            return data.get('template')
        except (json.JSONDecodeError, IOError):
            # If any errors, just return None and we'll create a new config
            return None
    
    def _store_current_template(self, template):
        """Stores the current template in the config file"""
        try:
            with open(self.config_file_path, 'w') as f:
                json.dump({'template': template}, f)
        except IOError:
            # If we can't write the file, just log a warning but continue
            ConanOutput().warning(
                f"Could not write package path configuration to {self.config_file_path}"
            )
