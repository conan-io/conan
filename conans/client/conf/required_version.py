from conans import __version__ as client_version
from conans.errors import ConanException
from conans.model.version import Version
from conans.model.version_range import VersionRange


def validate_conan_version(required_range):
    clientver = Version(client_version)
    version_range = VersionRange(required_range)
    for conditions in version_range.condition_sets:
        conditions.prerelease = True
    if not version_range.contains(clientver, resolve_prerelease=None):
        raise ConanException("Current Conan version ({}) does not satisfy "
                             "the defined one ({}).".format(clientver, required_range))


def check_required_conan_version(global_conf):
    """ Check if the required Conan version in config file matches to the current Conan version

            When required_conan_version is not configured, it's skipped
            When required_conan_version is configured, Conan's version must matches the required
            version
            When it doesn't match, an ConanException is raised

        :param global_conf: the global configura
        :return: None
    """
    required_range_new = global_conf.get("core:required_conan_version")
    if required_range_new:
        validate_conan_version(required_range_new)
