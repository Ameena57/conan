import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.env import environment_update


def test_missing_subarguments():
    """ config MUST run  with a subcommand. Otherwise, it MUST exits with error.
    """
    client = TestClient()
    client.run("config", assert_error=True)
    assert "ERROR: Exiting with code: 2" in client.out


def test_config_home_default():
    """ config home MUST show conan home path
    """
    client = TestClient()
    client.run("config home")
    assert client.cache.cache_folder in client.out
    client.run("config home --format=text")
    assert client.cache.cache_folder == client.stdout


def test_config_home_custom_home_dir():
    """ config home MUST accept CONAN_HOME as custom home path
    """
    cache_folder = os.path.join(temp_folder(), "custom")
    with environment_update({"CONAN_HOME": cache_folder}):
        client = TestClient(cache_folder=cache_folder)
        client.run("config home")
        assert cache_folder in client.out
        client.run("config home --format=text")
        assert client.cache.cache_folder == client.stdout


def test_config_home_custom_install():
    """ config install MUST accept CONAN_HOME as custom home path
    """
    cache_folder = os.path.join(temp_folder(), "custom")
    with environment_update({"CONAN_HOME": cache_folder}):
        client = TestClient(cache_folder=cache_folder)
        client.save({"conanfile.py": GenConanfile()})
        client.run("install .")
        assert "Installing (downloading, building) binaries" in client.out
