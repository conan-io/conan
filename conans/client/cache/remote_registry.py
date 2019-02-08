import json
import os
from collections import OrderedDict, namedtuple

import fasteners

from conans.errors import ConanException, NoRemoteAvailable
from conans.util.config_parser import get_bool_from_text_value
from conans.util.files import load, save
from conans.util.log import logger

default_remotes = OrderedDict({"conan-center": ("https://conan.bintray.com", True)})

Remote = namedtuple("Remote", "name url verify_ssl")


def load_registry_txt(contents):
    """Remove in Conan 2.0"""
    remotes = OrderedDict()
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
            remotes[remote_name] = (url, verify_ssl)
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


class _RemotesRegistry(object):

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        if force:
            return self._upsert(remote_name, url, verify_ssl, insert)

        def exists_function(remotes):
            if remote_name in remotes:
                raise ConanException("Remote '%s' already exists in remotes (use update to modify)"
                                     % remote_name)
        self._add_update(remote_name, url, verify_ssl, exists_function, insert)

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        def exists_function(remotes):
            if remote_name not in remotes:
                raise ConanException("Remote '%s' not found in remotes" % remote_name)
        self._add_update(remote_name, url, verify_ssl, exists_function, insert)

    def define(self, remotes):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            _, refs, prefs = self._load()
            refs = {k: v for k, v in refs.items() if v in remotes}
            self._save(remotes, refs, prefs)

    def _add_update(self, remote_name, url, verify_ssl, exists_function, insert=None):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, refs, prefs = self._load()
            exists_function(remotes)
            urls = {r[0]: name for name, r in remotes.items() if name != remote_name}
            if url in urls:
                raise ConanException("Remote '%s' already exists with same URL" % urls[url])
            if insert is not None:
                try:
                    insert_index = int(insert)
                except ValueError:
                    raise ConanException("insert argument must be an integer")
                remotes.pop(remote_name, None)  # Remove if exists (update)
                remotes_list = list(remotes.items())
                remotes_list.insert(insert_index, (remote_name, (url, verify_ssl)))
                remotes = OrderedDict(remotes_list)
            else:
                remotes[remote_name] = (url, verify_ssl)
            self._save(remotes, refs, prefs)

    def _upsert(self, remote_name, url, verify_ssl, insert):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, refs, prefs = self._load()
            # Remove duplicates
            remotes.pop(remote_name, None)
            remotes_list = []
            renamed = None
            for name, r in remotes.items():
                if r[0] != url:
                    remotes_list.append((name, r))
                else:
                    renamed = name

            if insert is not None:
                try:
                    insert_index = int(insert)
                except ValueError:
                    raise ConanException("insert argument must be an integer")
                remotes_list.insert(insert_index, (remote_name, (url, verify_ssl)))
                remotes = OrderedDict(remotes_list)
            else:
                remotes = OrderedDict(remotes_list)
                remotes[remote_name] = (url, verify_ssl)

            if renamed:
                for k, v in refs.items():
                    if v == renamed:
                        refs[k] = remote_name
            self._save(remotes, refs, prefs)


class RemoteRegistry(object):

    def __init__(self, cache, output):
        self._cache = cache
        self._filename = cache.registry_path
        self._output = output
        self._remotes = None

    @property
    def remotes(self):
        if self._remotes is None:
            data = json.loads(load(self._filename))
            self._remotes = OrderedDict()
            for r in data.get("remotes", []):
                self._remotes[r["name"]] = Remote(r["name"], r["url"], r["verify_ssl"])
        return self._remotes

    @property
    def default(self):
        try:
            return next(iter(self.remotes))
        except StopIteration:
            raise NoRemoteAvailable("No default remote defined in %s" % self._filename)

    def get(self, remote_name):
        try:
            return self.remotes[remote_name]
        except KeyError:
            raise NoRemoteAvailable("No remote '%s' defined in remotes in file %s"
                                    % (remote_name, self._filename))

    def remove(self, remote_name):
        self.get(remote_name)
        del self._remotes[remote_name]
        self._save()

    def _upsert(self, remote_name, url, verify_ssl, insert):
        # Remove duplicates
        updated_remote = Remote(remote_name, url, verify_ssl)
        remotes = self.remotes
        remotes.pop(remote_name, None)
        remotes_list = []
        renamed = None
        for name, r in remotes.items():
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
            remotes = OrderedDict(remotes_list)
        else:
            remotes = OrderedDict(remotes_list)
            remotes[remote_name] = updated_remote

        if renamed:
            for k, v in refs.items():
                if v == renamed:
                    refs[k] = remote_name
        self._save()

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        if force:
            return self._upsert(remote_name, url, verify_ssl, insert)

        if remote_name in self.remotes:
            raise ConanException("Remote '%s' already exists in remotes (use update to modify)"
                                 % remote_name)
        self._add_update(remote_name, url, verify_ssl, insert)

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        if remote_name not in self.remotes:
            raise ConanException("Remote '%s' not found in remotes" % remote_name)
        self._add_update(remote_name, url, verify_ssl, insert)

    def _add_update(self, remote_name, url, verify_ssl, insert=None):
        remotes = self.remotes
        urls = {r.url: name for name, r in remotes.items() if name != remote_name}
        if url in urls:
            raise ConanException("Remote '%s' already exists with same URL" % urls[url])
        updated_remote = Remote(remote_name, url, verify_ssl)
        if insert is not None:
            try:
                insert_index = int(insert)
            except ValueError:
                raise ConanException("insert argument must be an integer")
            remotes.pop(remote_name, None)  # Remove if exists (update)
            remotes_list = list(remotes.items())
            remotes_list.insert(insert_index, updated_remote)
            self._remotes = OrderedDict(remotes_list)
        else:
            remotes[remote_name] = updated_remote
        self._save()

    def _save(self):
        ret = {"remotes": [{"name": r, "url": u, "verify_ssl": v}
                           for r, (u, v) in self._remotes.items()]}
        return json.dumps(ret, indent=True)

    def clean(self):
        self._remotes = {}
        self._save()

    def rename(self, remote_name, new_remote_name):
        remotes = self.remotes
        if new_remote_name in remotes:
            raise ConanException("Remote '%s' already exists" % new_remote_name)

        try:
            remote = remotes.pop(remote_name)
        except KeyError:
            raise ConanException("Remote '%s' not found in remotes" % remote_name)

        new_remote = Remote(new_remote_name, remote.url, remote.verify_ssl)
        self._remotes[new_remote_name] = new_remote

        for ref in self._cache.all_refs():
            with self._cache.package_layout(ref).update_metadata() as metadata:
                if metadata.recipe.remote.name == remote_name:
                    metadata.recipe.remote = new_remote
                for pkg_metadata in metadata.packages.values():
                    if pkg_metadata.remote.name == remote_name:
                        pkg_metadata.remote = new_remote
        self._save()

    @property
    def ref_list(self):
        pass
