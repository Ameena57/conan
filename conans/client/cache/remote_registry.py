import json
import os
from collections import OrderedDict, namedtuple

from conans.errors import ConanException, NoRemoteAvailable
from conans.util.config_parser import get_bool_from_text_value
from conans.util.files import load, save
from conans.model.ref import PackageReference

default_remotes = OrderedDict({"conan-center": ("https://conan.bintray.com", True)})

Remote = namedtuple("Remote", "name url verify_ssl")


def load_registry_txt(contents):
    """Remove in Conan 2.0"""
    remotes = Remotes()
    refs = {}
    end_remotes = False
    # Parse the file
    for line in contents.splitlines():
        line = line.strip()

        if not line:
            if end_remotes:
                raise ConanException("Bad file format, blank line")
            end_remotes = True
            continue
        chunks = line.split()
        if not end_remotes:
            if len(chunks) == 2:  # Retro compatibility
                remote_name, url = chunks
                verify_ssl = "True"
            elif len(chunks) == 3:
                remote_name, url, verify_ssl = chunks
            else:
                raise ConanException("Bad file format, wrong item numbers in line '%s'" % line)

            verify_ssl = get_bool_from_text_value(verify_ssl)
            remotes.add(remote_name, url, verify_ssl)
        else:
            ref, remote_name = chunks
            refs[ref] = remote_name

    return remotes, refs


def dump_registry(remotes, refs, prefs):
    """To json"""
    ret = {"remotes": [{"name": r, "url": u, "verify_ssl": v} for r, (u, v) in remotes.items()],
           "references": refs,
           "package_references": prefs}

    return json.dumps(ret, indent=True)


def load_registry(contents):
    """From json"""
    data = json.loads(contents)
    remotes = OrderedDict()
    refs = data.get("references", {})
    prefs = data.get("package_references", {})
    for r in data["remotes"]:
        remotes[r["name"]] = (r["url"], r["verify_ssl"])
    return remotes, refs, prefs


def migrate_registry_file(path, new_path):
    try:
        remotes, refs = load_registry_txt(load(path))
        save(new_path, dump_registry(remotes, refs, {}))
    except Exception as e:
        raise ConanException("Cannot migrate registry.txt to registry.json: %s" % str(e))
    else:
        os.unlink(path)


class Remotes(object):
    def __init__(self):
        self._remotes = OrderedDict()

    def clear(self):
        self._remotes.clear()

    def items(self):
        return self._remotes.items()

    def values(self):
        return self._remotes.values()

    @staticmethod
    def loads(text):
        result = Remotes()
        data = json.loads(text)
        for r in data.get("remotes", []):
            result._remotes[r["name"]] = Remote(r["name"], r["url"], r["verify_ssl"])
        return result

    def save(self, filename):
        ret = {"remotes": [{"name": r, "url": u, "verify_ssl": v}
                           for r, (_, u, v) in self._remotes.items()]}
        save(filename, json.dumps(ret, indent=True))

    def _get_by_url(self, url):
        for name, remote in self._remotes.items():
            if remote.url == url:
                return name

    def rename(self, remote_name, new_remote_name):
        if new_remote_name in self._remotes:
            raise ConanException("Remote '%s' already exists" % new_remote_name)

        remote = self._remotes[remote_name]
        new_remote = Remote(new_remote_name, remote.url, remote.verify_ssl)
        self._remotes = OrderedDict([(new_remote_name, new_remote) if k == remote_name
                                     else (k, v) for k, v in self._remotes.items()])

    @property
    def default(self):
        try:
            return self._remotes[next(iter(self._remotes))]
        except StopIteration:
            raise NoRemoteAvailable("No default remote defined")

    def __contains__(self, remote_name):
        return remote_name in self._remotes

    def get(self, remote_name):
        return self._remotes.get(remote_name)

    def __getitem__(self, remote_name):
        try:
            return self._remotes[remote_name]
        except KeyError:
            raise NoRemoteAvailable("No remote '%s' defined in remotes" % (remote_name))

    def __delitem__(self, remote_name):
        try:
            del self._remotes[remote_name]
        except KeyError:
            raise NoRemoteAvailable("No remote '%s' defined in remotes" % (remote_name))

    def _upsert(self, remote_name, url, verify_ssl, insert):
        # Remove duplicates
        updated_remote = Remote(remote_name, url, verify_ssl)
        self._remotes.pop(remote_name, None)
        remotes_list = []
        renamed = None
        for name, r in self._remotes.items():
            if r[0] != url:
                remotes_list.append((name, r))
            else:
                renamed = name

        if insert is not None:
            try:
                insert_index = int(insert)
            except ValueError:
                raise ConanException("insert argument must be an integer")
            remotes_list.insert(insert_index, updated_remote)
            self._remotes = OrderedDict(remotes_list)
        else:
            self._remotes = OrderedDict(remotes_list)
            self._remotes[remote_name] = updated_remote

        if renamed:
            for k, v in refs.items():
                if v == renamed:
                    refs[k] = remote_name
        self._save()

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        if force:
            return self._upsert(remote_name, url, verify_ssl, insert)

        if remote_name in self._remotes:
            raise ConanException("Remote '%s' already exists in remotes (use update to modify)"
                                 % remote_name)
        prev_remote_name = self._get_by_url(url)
        if prev_remote_name:
            raise ConanException("Remote '%s' already exists with same URL" % prev_remote_name)
        self._add_update(remote_name, url, verify_ssl, insert)

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        if remote_name not in self._remotes:
            raise ConanException("Remote '%s' not found in remotes" % remote_name)
        self._add_update(remote_name, url, verify_ssl, insert)

    def _add_update(self, remote_name, url, verify_ssl, insert=None):
        updated_remote = Remote(remote_name, url, verify_ssl)
        if insert is not None:
            try:
                insert_index = int(insert)
            except ValueError:
                raise ConanException("insert argument must be an integer")
            self._remotes.pop(remote_name, None)  # Remove if exists (update)
            remotes_list = list(self._remotes.items())
            remotes_list.insert(insert_index, (remote_name, updated_remote))
            self._remotes = OrderedDict(remotes_list)
        else:
            self._remotes[remote_name] = updated_remote


class RemoteRegistry(object):

    def __init__(self, cache):
        self._cache = cache
        self._filename = cache.registry_path

    def load_remotes(self):
        content = load(self._filename)
        return Remotes.loads(content)

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        remotes = self.load_remotes()
        remotes.add(remote_name, url, verify_ssl, insert, force)
        remotes.save(self._filename)
        # FIXME: Missing something to do with REFS

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        remotes = self.load_remotes()
        remotes.update(remote_name, url, verify_ssl, insert)
        remotes.save(self._filename)

    def clear(self):
        remotes = self.load_remotes()
        remotes.clear()
        for ref in self._cache.all_refs():
            with self._cache.package_layout(ref).update_metadata() as metadata:
                metadata.recipe.remote = None
                for pkg_metadata in metadata.packages.values():
                    pkg_metadata.remote = None
        remotes.save(self._filename)

    def remove(self, remote_name):
        remotes = self.load_remotes()
        del remotes[remote_name]

        for ref in self._cache.all_refs():
            with self._cache.package_layout(ref).update_metadata() as metadata:
                if metadata.recipe.remote == remote_name:
                    metadata.recipe.remote = None
                for pkg_metadata in metadata.packages.values():
                    if pkg_metadata.remote == remote_name:
                        pkg_metadata.remote = None

        remotes.save(self._filename)

    def define(self, remotes):
        # For definition from conan config install
        for ref in self._cache.all_refs():
            with self._cache.package_layout(ref).update_metadata() as metadata:
                if metadata.recipe.remote not in remotes:
                    metadata.recipe.remote = None
                for pkg_metadata in metadata.packages.values():
                    if pkg_metadata.remote not in remotes:
                        pkg_metadata.remote = None

        remotes.save(self._filename)

    def rename(self, remote_name, new_remote_name):
        remotes = self.load_remotes()
        remotes.rename(remote_name, new_remote_name)

        for ref in self._cache.all_refs():
            with self._cache.package_layout(ref).update_metadata() as metadata:
                if metadata.recipe.remote == remote_name:
                    metadata.recipe.remote = new_remote_name
                for pkg_metadata in metadata.packages.values():
                    if pkg_metadata.remote == remote_name:
                        pkg_metadata.remote = new_remote_name

        remotes.save(self._filename)

    @property
    def refs_list(self):
        result = {}
        for ref in self._cache.all_refs():
            metadata = self._cache.package_layout(ref).load_metadata()
            if metadata.recipe.remote:
                result[ref] = metadata.recipe.remote
        return result

    @property
    def prefs_list(self):
        result = {}
        for ref in self._cache.all_refs():
            metadata = self._cache.package_layout(ref).load_metadata()
            for pid, pkg_metadata in metadata.packages.items():
                pref = PackageReference(ref, pid)
                result[pref] = pkg_metadata.remote
        return result
