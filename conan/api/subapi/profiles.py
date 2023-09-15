import os

from conans.client.cache.cache import ClientCache
from conans.client.profile_loader import ProfileLoader
from conans.model.profile import Profile


class ProfilesAPI:

    def __init__(self, conan_api):
        self._conan_api = conan_api

    def get_default_host(self):
        """
        :return: the path to the default "host" profile, either in the cache or as defined
            by the user in configuration
        """
        cache = ClientCache(self._conan_api.cache_folder)
        loader = ProfileLoader(cache)
        return loader.get_default_host()

    def get_default_build(self):
        """
        :return: the path to the default "build" profile, either in the cache or as
            defined by the user in configuration
        """
        cache = ClientCache(self._conan_api.cache_folder)
        loader = ProfileLoader(cache)
        return loader.get_default_build()

    def get_profiles_from_args(self, args):
        all_profiles = [] if not args.profile_all else args.profile_all
        all_settings = [] if not args.settings_all else args.settings_all
        all_options = [] if not args.options_all else args.options_all
        all_conf = [] if not args.conf_all else args.conf_all

        build_profiles = all_profiles + ([self.get_default_build()] if not args.profile_build else args.profile_build)
        build_settings = all_settings + ([] if not args.settings_build else args.settings_build)
        build_options = all_options + ([] if not args.options_build else args.options_build)
        build_conf = all_conf + ([] if not args.conf_build else args.conf_build)

        host_profiles = all_profiles + ([self.get_default_host()] if not args.profile_host else args.profile_host)
        host_settings = all_settings + ([] if not args.settings_host else args.settings_host)
        host_options = all_options + ([] if not args.options_host else args.options_host)
        host_conf = all_conf + ([] if not args.conf_host else args.conf_host)

        profile_build = self.get_profile(profiles=build_profiles, settings=build_settings,
                                         options=build_options, conf=build_conf)

        profile_host = self.get_profile(profiles=host_profiles, settings=host_settings,
                                        options=host_options, conf=host_conf)
        return profile_host, profile_build

    def get_profile(self, profiles, settings=None, options=None, conf=None, cwd=None):
        """ Computes a Profile as the result of aggregating all the user arguments, first it
        loads the "profiles", composing them in order (last profile has priority), and
        finally adding the individual settings, options (priority over the profiles)
        """
        assert isinstance(profiles, list), "Please provide a list of profiles"
        cache = ClientCache(self._conan_api.cache_folder)
        loader = ProfileLoader(cache)
        profile = loader.from_cli_args(profiles, settings, options, conf, cwd)
        profile.conf.validate()
        cache.new_config.validate()
        # Apply the new_config to the profiles the global one, so recipes get it too
        profile.conf.rebase_conf_definition(cache.new_config)
        return profile

    def get_path(self, profile, cwd=None, exists=True):
        """
        :return: the resolved path of the given profile name, that could be in the cache,
            or local, depending on the "cwd"
        """
        cache = ClientCache(self._conan_api.cache_folder)
        loader = ProfileLoader(cache)
        cwd = cwd or os.getcwd()
        profile_path = loader.get_profile_path(profile, cwd, exists=exists)
        return profile_path

    def list(self):
        """
        List all the profiles file sin the cache
        :return: an alphabetically ordered list of profile files in the default cache location
        """
        # List is to be extended (directories should not have a trailing slash)
        paths_to_ignore = ['.DS_Store']

        profiles = []
        cache = ClientCache(self._conan_api.cache_folder)
        profiles_path = cache.profiles_path
        if os.path.exists(profiles_path):
            for current_directory, _, files in os.walk(profiles_path, followlinks=True):
                files = filter(lambda file: os.path.relpath(
                    os.path.join(current_directory, file), profiles_path) not in paths_to_ignore, files)

                for filename in files:
                    rel_path = os.path.relpath(os.path.join(current_directory, filename),
                                               profiles_path)
                    profiles.append(rel_path)

        profiles.sort()
        return profiles

    @staticmethod
    def detect():
        """
        :return: an automatically detected Profile, with a "best guess" of the system settings
        """
        profile = Profile()
        from conans.client.conf.detect import detect_defaults_settings
        settings = detect_defaults_settings()
        for name, value in settings:
            profile.settings[name] = value
        # TODO: This profile is very incomplete, it doesn't have the processed_settings
        #  good enough at the moment for designing the API interface, but to improve
        return profile
