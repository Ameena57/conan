import copy
import os
from io import StringIO
from typing import List

from jinja2 import Environment, select_autoescape, FileSystemLoader, ChoiceLoader

from conan.cache.cache import DataCache
from conan.cache.conan_reference_layout import RecipeLayout, PackageLayout
from conans.assets.templates import dict_loader
from conans.cli.output import ConanOutput
from conans.client.cache.editable import EditablePackages
from conans.client.cache.remote_registry import RemoteRegistry
from conans.client.conf import ConanClientConfigParser, get_default_client_conf, \
    get_default_settings_yml
from conans.client.store.localdb import LocalDB
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.model.settings import Settings
from conans.paths import ARTIFACTS_PROPERTIES_FILE, DEFAULT_PROFILE_NAME
from conans.util.files import load, normalize, save, remove, mkdir


CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REMOTES = "remotes.json"
PROFILES_FOLDER = "profiles"
HOOKS_FOLDER = "hooks"
TEMPLATES_FOLDER = "templates"
GENERATORS_FOLDER = "generators"


class ClientCache(object):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, cache_folder):
        self.cache_folder = cache_folder
        self._output = ConanOutput()

        # Caching
        self._config = None
        self._new_config = None
        self.editable_packages = EditablePackages(self.cache_folder)
        # paths
        self._store_folder = os.path.join(self.cache_folder, "p")

        mkdir(self._store_folder)
        db_filename = os.path.join(self._store_folder, 'cache.sqlite3')
        self._data_cache = DataCache(self._store_folder, db_filename)

    def closedb(self):
        self._data_cache.closedb()

    def dump(self):
        out = StringIO()
        self._data_cache.dump(out)
        return out.getvalue()

    def assign_rrev(self, layout: RecipeLayout):
        return self._data_cache.assign_rrev(layout)

    def assign_prev(self, layout: PackageLayout):
        return self._data_cache.assign_prev(layout)

    def ref_layout(self, ref: RecipeReference):
        # It must exists
        assert ref.revision is not None
        return self._data_cache.get_reference_layout(ref)

    def pkg_layout(self, ref: PkgReference):
        return self._data_cache.get_package_layout(ref)

    def create_export_recipe_layout(self, ref: RecipeReference):
        return self._data_cache.create_export_recipe_layout(ref)

    def create_temp_pkg_layout(self, ref):
        return self._data_cache.create_tmp_package_layout(ref)

    def get_or_create_ref_layout(self, ref: RecipeReference):
        return self._data_cache.get_or_create_ref_layout(ref)

    def get_or_create_pkg_layout(self, ref: PkgReference):
        return self._data_cache.get_or_create_pkg_layout(ref)

    def remove_recipe_layout(self, layout):
        self._data_cache.remove_recipe(layout)

    def remove_package_layout(self, layout):
        self._data_cache.remove_package(layout)

    def get_recipe_timestamp(self, ref):
        return self._data_cache.get_recipe_timestamp(ref)

    def get_package_timestamp(self, ref):
        return self._data_cache.get_package_timestamp(ref)

    def update_recipe_timestamp(self, ref):
        """ when the recipe already exists in cache, but we get a new timestamp from a server
        that would affect its order in our cache """
        return self._data_cache.update_recipe_timestamp(ref)

    def set_package_timestamp(self, pref):
        return self._data_cache.update_package_timestamp(pref)

    def all_refs(self):
        return self._data_cache.list_references()

    def exists_rrev(self, ref):
        return self._data_cache.exists_rrev(ref)

    def exists_prev(self, pref):
        return self._data_cache.exists_prev(pref)

    def get_package_revisions_references(self, ref, only_latest_prev=False):
        return self._data_cache.get_package_revisions_references(ref, only_latest_prev)

    def get_package_references(self, ref: RecipeReference) -> List[PkgReference]:
        return self._data_cache.get_package_references(ref)

    def get_build_id(self, ref):
        return self._data_cache.get_build_id(ref)

    def get_recipe_revisions_references(self, ref, only_latest_rrev=False):
        return self._data_cache.get_recipe_revisions_references(ref, only_latest_rrev)

    def get_latest_recipe_reference(self, ref):
        return self._data_cache.get_recipe_revisions_references(ref)

    def get_latest_package_reference(self, ref):
        return self._data_cache.get_package_revisions_references(ref)

    @property
    def store(self):
        return self._store_folder

    def editable_path(self, ref):
        _tmp = copy.copy(ref)
        _tmp.revision = None
        edited_ref = self.editable_packages.get(_tmp)
        if edited_ref:
            conanfile_path = edited_ref["path"]
            return conanfile_path

    def installed_as_editable(self, ref):
        _tmp = copy.copy(ref)
        _tmp.revision = None
        edited_ref = self.editable_packages.get(_tmp)
        return bool(edited_ref)

    @property
    def config_install_file(self):
        return os.path.join(self.cache_folder, "config_install.json")

    @property
    def remotes_path(self):
        return os.path.join(self.cache_folder, REMOTES)

    @property
    def remotes_registry(self) -> RemoteRegistry:
        return RemoteRegistry(self)

    @property
    def artifacts_properties_path(self):
        return os.path.join(self.cache_folder, ARTIFACTS_PROPERTIES_FILE)

    def read_artifacts_properties(self):
        ret = {}
        if not os.path.exists(self.artifacts_properties_path):
            save(self.artifacts_properties_path, "")
            return ret
        try:
            contents = load(self.artifacts_properties_path)
            for line in contents.splitlines():
                if line and not line.strip().startswith("#"):
                    tmp = line.split("=", 1)
                    if len(tmp) != 2:
                        raise Exception()
                    name = tmp[0].strip()
                    value = tmp[1].strip()
                    ret[str(name)] = str(value)
            return ret
        except Exception:
            raise ConanException("Invalid %s file!" % self.artifacts_properties_path)

    @property
    def config(self):
        if not self._config:
            self.initialize_config()
            self._config = ConanClientConfigParser(self.conan_conf_path)
        return self._config

    @property
    def new_config_path(self):
        return os.path.join(self.cache_folder, "global.conf")

    @property
    def new_config(self):
        """ this is the new global.conf to replace the old conan.conf that contains
        configuration defined with the new syntax as in profiles, this config will be composed
        to the profile ones and passed to the conanfiles.conf, which can be passed to collaborators
        """
        if self._new_config is None:
            self._new_config = ConfDefinition()
            if os.path.exists(self.new_config_path):
                self._new_config.loads(load(self.new_config_path))
        return self._new_config

    @property
    def localdb(self):
        localdb_filename = os.path.join(self.cache_folder, LOCALDB)
        encryption_key = os.getenv('CONAN_LOGIN_ENCRYPTION_KEY', None)
        return LocalDB.create(localdb_filename, encryption_key=encryption_key)

    @property
    def conan_conf_path(self):
        return os.path.join(self.cache_folder, CONAN_CONF)

    @property
    def profiles_path(self):
        return os.path.join(self.cache_folder, PROFILES_FOLDER)

    @property
    def settings_path(self):
        return os.path.join(self.cache_folder, CONAN_SETTINGS)

    @property
    def generators_path(self):
        return os.path.join(self.cache_folder, GENERATORS_FOLDER)

    @property
    def default_profile_path(self):
        # Used only in testing, and this class "reset_default_profile"
        return os.path.join(self.cache_folder, PROFILES_FOLDER, DEFAULT_PROFILE_NAME)

    @property
    def hooks_path(self):
        """
        :return: Hooks folder in client cache
        """
        return os.path.join(self.cache_folder, HOOKS_FOLDER)

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings without values"""
        self.initialize_settings()
        content = load(self.settings_path)
        return Settings.loads(content)

    @property
    def hooks(self):
        """Returns a list of hooks inside the hooks folder"""
        hooks = []
        for hook_name in os.listdir(self.hooks_path):
            if os.path.isfile(hook_name) and hook_name.endswith(".py"):
                hooks.append(hook_name[:-3])
        return hooks

    @property
    def generators(self):
        """Returns a list of generator paths inside the generators folder"""
        generators = []
        if os.path.exists(self.generators_path):
            for path in os.listdir(self.generators_path):
                generator = os.path.join(self.generators_path, path)
                if os.path.isfile(generator) and generator.endswith(".py"):
                    generators.append(generator)
        return generators

    def get_template(self, template_name, user_overrides=False):
        # TODO: It can be initialized only once together with the Conan app
        loaders = [dict_loader]
        if user_overrides:
            loaders.insert(0, FileSystemLoader(os.path.join(self.cache_folder, 'templates')))
        env = Environment(loader=ChoiceLoader(loaders),
                          autoescape=select_autoescape(['html', 'xml']))
        return env.get_template(template_name)

    def initialize_config(self):
        if not os.path.exists(self.conan_conf_path):
            save(self.conan_conf_path, normalize(get_default_client_conf()))

    def reset_config(self):
        if os.path.exists(self.conan_conf_path):
            remove(self.conan_conf_path)
        self.initialize_config()

    def reset_default_profile(self):
        if os.path.exists(self.default_profile_path):
            remove(self.default_profile_path)

    def initialize_settings(self):
        if not os.path.exists(self.settings_path):
            save(self.settings_path, normalize(get_default_settings_yml()))

    def reset_settings(self):
        if os.path.exists(self.settings_path):
            remove(self.settings_path)
        self.initialize_settings()
