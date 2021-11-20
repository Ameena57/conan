from conans.client.cache.cache import ClientCache
from conans import __version__ as client_version
from conans.errors import ConanException
from conans.model.version import Version
from conans.model.version_range import VersionRange

client_version = Version(client_version)


def validate_conan_version(required_range):
    if client_version not in VersionRange(required_range):
        raise ConanException("Current Conan version ({}) does not satisfy "
                             "the defined one ({}).".format(client_version, required_range))


def check_required_conan_version(cache_folder):
    """ Check if the required Conan version in config file matches to the current Conan version

            When required_conan_version is not configured, it's skipped
            When required_conan_version is configured, Conan's version must matches the required
            version
            When it doesn't match, an ConanException is raised

        :param cache_folder: Conan cache folder
        :param out: Output stream
        :return: None
    """
    cache = ClientCache(cache_folder)
    required_range = cache.config.required_conan_version
    if required_range:
        validate_conan_version(required_range)

    required_range_new = cache.new_config["core:required_conan_version"]
    if required_range_new:
        validate_conan_version(required_range_new)
