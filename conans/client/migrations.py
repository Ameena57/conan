from conans.client.client_cache import CONAN_CONF, PROFILES_FOLDER
from conans.errors import ConanException
from conans.migrations import Migrator
from conans.paths import DEFAULT_PROFILE_NAME
from conans.util.files import load, save
from conans.model.version import Version
import os
from conans.client.conf import default_settings_yml


class ClientMigrator(Migrator):

    def __init__(self, client_cache, current_version, out):
        self.client_cache = client_cache
        super(ClientMigrator, self).__init__(client_cache.conan_folder, client_cache.store,
                                             current_version, out)

    def _update_settings_yml(self, old_settings):
        settings_path = self.client_cache.settings_path
        if not os.path.exists(settings_path):
            self.out.warn("Migration: This conan installation doesn't have settings yet")
            self.out.warn("Nothing to migrate here, settings will be generated automatically")
            return

        current_settings = load(self.client_cache.settings_path)
        if current_settings != default_settings_yml:
            self.out.warn("Migration: Updating settings.yml")
            if current_settings != old_settings:
                backup_path = self.client_cache.settings_path + ".backup"
                save(backup_path, current_settings)
                self.out.warn("*" * 40)
                self.out.warn("A new settings.yml has been defined")
                self.out.warn("Your old settings.yml has been backup'd to: %s" % backup_path)
                self.out.warn("*" * 40)
            save(self.client_cache.settings_path, default_settings_yml)

    def _make_migrations(self, old_version):
        # ############### FILL THIS METHOD WITH THE REQUIRED ACTIONS ##############
        # VERSION 0.1
        if old_version is None:
            return

        if old_version < Version("0.25"):
            old_settings = """
os:
    Windows:
    Linux:
    Macos:
    Android:
        api_level: ANY
    iOS:
        version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3"]
    FreeBSD:
    SunOS:
arch: [x86, x86_64, ppc64le, ppc64, armv6, armv7, armv7hf, armv8, sparc, sparcv9, mips, mips64]
compiler:
    sun-cc:
       version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
       threads: [None, posix]
       libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc:
        version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3", "5.4", "6.1", "6.2", "6.3", "7.1"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release]
"""
            self._update_settings_yml(old_settings)

        if old_version < Version("0.20"):
            if os.path.exists(os.path.join(self.client_cache.conan_folder, CONAN_CONF)):
                raise ConanException("Migration: Your Conan version was too old, "
                                     "please, remove the %s file manually, Conan will generate "
                                     "a new one." % CONAN_CONF)

        if old_version < Version("0.25"):
            self.out.warn("Migration: Moving default settings from %s file to %s"
                          % (CONAN_CONF, DEFAULT_PROFILE_NAME))
            conf_path = os.path.join(self.client_cache.conan_folder, CONAN_CONF)
            default_profile_path = os.path.join(self.client_cache.conan_folder, PROFILES_FOLDER,
                                                DEFAULT_PROFILE_NAME)
            migrate_to_default_profile(conf_path, default_profile_path)


def migrate_to_default_profile(conf_path, default_profile_path):
    tag = "[settings_defaults]"
    old_conf = load(conf_path)
    if tag not in old_conf:
        return
    tmp = old_conf.find(tag)
    new_conf = old_conf[0:tmp]
    rest = old_conf[tmp + len(tag):]
    if tmp:
        if "]" in rest:  # More sections after the settings_defaults
            new_conf += rest[rest.find("["):]
            save(conf_path, new_conf)
            settings = rest[:rest.find("[")].strip()
        else:
            save(conf_path, new_conf)
            settings = rest.strip()
        # Now generate the default profile from the read settings_defaults
        new_profile = "[settings]\n%s" % settings
        save(default_profile_path, new_profile)
