from conans.client.cache.cache import ClientCache
from semver import satisfies
from conans import __version__ as client_version
from conans.errors import ConanException


def validate_conan_version(required_range):
    result = satisfies(client_version, required_range, loose=True, include_prerelease=True)
    if not result:
        raise ConanException("Current Conan version ({}) does not satisfy "
                             "the defined one ({}).".format(client_version, required_range))


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
    required_range = cache.config.required_conan_version
    if required_range:
        validate_conan_version(required_range)

