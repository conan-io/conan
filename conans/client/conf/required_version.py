from conans.client.cache.cache import ClientCache
from semver import satisfies, Range
from conans import __version__ as client_version
from conans.errors import ConanException


def check_required_conan_version(cache_folder, out):
    """ Check if the required Conan version in config file matches to the current Conan version

            When required_conan_version is not configured, it's skipped
            When required_conan_version is configured, Conan's version must matches the required
            version
            When it doesn't match, an ConanException is raised

        :param cache_folder: Conan cache folder
        :param out: Output stream
        :return: None
    """
    cache = ClientCache(cache_folder, out)
    required_version = cache.config.required_conan_version
    if required_version:
        try:
            Range(required_version, False)
        except ValueError:
            raise ConanException("The required version expression '{}' is not valid."
                                 .format(required_version))
        result = satisfies(client_version, required_version)
        if not result:
            raise ConanException("The current Conan version ({}) does not match to the required"
                                 " version ({}).".format(client_version, required_version))
