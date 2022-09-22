from collections import OrderedDict

from conans.errors import conanfile_exception_formatter


class BinaryCompatibility:
    def __init__(self, cache):
        pass

    def compatibles(self, conanfile):
        compat_infos = []
        if hasattr(conanfile, "compatibility") and callable(conanfile.compatibility):
            with conanfile_exception_formatter(conanfile, "compatibility"):
                recipe_compatibles = conanfile.compatibility()
                compat_infos.extend(self._compatible_infos(conanfile, recipe_compatibles))

        conanfile.compatible_packages.extend(compat_infos)

    @staticmethod
    def _compatible_infos(conanfile, compatibles):
        result = []
        if compatibles:
            for elem in compatibles:
                compat_info = conanfile.original_info.clone()
                settings = elem.get("settings")
                if settings:
                    compat_info.settings.update_values(settings)
                options = elem.get("options")
                if options:
                    from conans.model.options import OptionsValues
                    new_options = OptionsValues(options)
                    compat_info.options.update(new_options)
                result.append(compat_info)
        return result
