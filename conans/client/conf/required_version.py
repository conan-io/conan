from conans.client.cache.cache import ClientCache
from conans.client.graph.range_resolver import satisfying
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
        output = ""
        result = satisfying([client_version], required_version, output)
        if not result:
            raise ConanException("The current Conan version ({}) does not match to the required version ({})."
                     .format(client_version, required_version))
        elif result != client_version:
            raise ConanException(result)
