import json
import os
from collections import OrderedDict, namedtuple

import fasteners

from conans.errors import ConanException, NoRemoteAvailable
from conans.model.ref import ConanFileReference, PackageReference
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


class _Registry(object):

    def __init__(self, filename, lockfile, output):
        self._filename = filename
        self._lockfile = lockfile
        self._output = output

    def _load(self):
        tmp = load(self._filename)
        return load_registry(tmp)

    def _save(self, remotes, refs, prefs):
        tmp = dump_registry(remotes, refs, prefs)
        save(self._filename, tmp)


class _GenericReferencesRegistry(_Registry):

    @staticmethod
    def _key(ref):
        return str(ref.copy_clear_rev())

    def remove(self, ref, quiet=False, remote_name=None):
        assert isinstance(ref, (ConanFileReference, PackageReference)), \
            "remote_registry needs known ref to remove"
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, refs = self._partial_load()
            try:
                if remote_name is None or remote_name == refs[str(ref)]:
                    refs.pop(self._key(ref), None)
                    self._partial_save(refs)
            except KeyError:
                if not quiet:
                    self._output.warn("Couldn't delete '%s' from remote registry" % str(ref))

    def get(self, ref):
        assert isinstance(ref, (ConanFileReference, PackageReference)), \
            "remote_registry needs known ref to get"
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, refs = self._partial_load()
            remote_name = refs.get(self._key(ref), None)
            if not remote_name:
                return None
            return Remote(remote_name, remotes[remote_name][0], remotes[remote_name][1])

    def set(self, ref, remote_name, check_exists=False):
        assert isinstance(ref, (ConanFileReference, PackageReference)), \
            "remote_registry needs known ref to set"
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, refs = self._partial_load()
            if check_exists and (self._key(ref) in refs):
                raise ConanException("%s already exists. Use update" % str(ref))
            if remote_name not in remotes:
                raise ConanException("%s not in remotes" % remote_name)

            refs.pop(self._key(ref), None)
            refs[self._key(ref)] = remote_name
            self._partial_save(refs)

    @property
    def list(self):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            _, refs = self._partial_load()
            return refs


class _ReferencesRegistry(_GenericReferencesRegistry):

    def _partial_load(self):
        """Loads only references for recipes"""
        remotes, rrefs, _ = self._load()
        return remotes, rrefs

    def _partial_save(self, refs):
        """Saves only modified references for recipes"""
        remotes, _, prefs = self._load()
        self._save(remotes, refs, prefs)

    def update(self, ref, remote_name):
        assert(isinstance(ref, ConanFileReference))
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, rrefs, prefs = self._load()
            if self._key(ref) not in rrefs:
                raise ConanException("%s does not exist. Use add" % str(ref))
            if remote_name not in remotes:
                raise ConanException("%s not in remotes" % remote_name)
            rrefs[self._key(ref)] = remote_name
            self._save(remotes, rrefs, prefs)


class _PackageReferencesRegistry(_GenericReferencesRegistry):

    def _partial_load(self):
        """Loads only references for packages"""
        remotes, _, prefs = self._load()
        return remotes, prefs

    def _partial_save(self, prefs):
        """Saves only modified references for packages"""
        remotes, refs, _ = self._load()
        self._save(remotes, refs, prefs)

    def update(self, pref, remote_name):
        assert(isinstance(pref, PackageReference))
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, rrefs, prefs = self._load()
            if self._key(pref) not in prefs:
                raise ConanException("%s does not exist. Use add" % str(pref))
            if remote_name not in remotes:
                raise ConanException("%s not in remotes" % remote_name)
            prefs[self._key(pref)] = remote_name
            self._save(remotes, rrefs, prefs)

    def remove_all(self, ref):
        assert(isinstance(ref, ConanFileReference))
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, rrefs, prefs = self._load()
            ret = {}
            for p, r in prefs.items():
                if PackageReference.loads(p).ref != ref.copy_clear_rev():
                    ret[p] = r
            self._save(remotes, rrefs, ret)


class _RemotesRegistry(_Registry):

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        if force:
            return self._upsert(remote_name, url, verify_ssl, insert)

        def exists_function(remotes):
            if remote_name in remotes:
                raise ConanException("Remote '%s' already exists in remotes (use update to modify)"
                                     % remote_name)
        self._add_update(remote_name, url, verify_ssl, exists_function, insert)

    def remove(self, remote_name):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, refs, prefs = self._load()
            if remote_name not in remotes:
                raise ConanException("Remote '%s' not found in remotes" % remote_name)
            del remotes[remote_name]
            refs = {k: v for k, v in refs.items() if v != remote_name}
            prefs = {k: v for k, v in prefs.items() if v != remote_name}
            self._save(remotes, refs, prefs)

    def clean(self):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            self._save({}, {}, {})

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        def exists_function(remotes):
            if remote_name not in remotes:
                raise ConanException("Remote '%s' not found in remotes" % remote_name)
        self._add_update(remote_name, url, verify_ssl, exists_function, insert)

    def rename(self, remote_name, new_remote_name):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, refs, prefs = self._load()
            if remote_name not in remotes:
                raise ConanException("Remote '%s' already exists" % new_remote_name)

            if remote_name not in remotes:
                raise ConanException("Remote '%s' not found in remotes" % remote_name)
            new_remotes = OrderedDict()
            for name, info in remotes.items():
                name = name if name != remote_name else new_remote_name
                new_remotes[name] = info
            remotes = new_remotes
            for k, v in refs.items():
                if v == remote_name:
                    refs[k] = new_remote_name
            self._save(remotes, refs, prefs)

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

    @property
    def default(self):
        try:
            return self.list[0]
        except IndexError:
            raise NoRemoteAvailable("No default remote defined in %s" % self._filename)

    @property
    def list(self):
        return list(self._remote_dict.values())

    def get(self, remote_name):
        try:
            return self._remote_dict[remote_name]
        except KeyError:
            raise NoRemoteAvailable("No remote '%s' defined in remotes in file %s"
                                    % (remote_name, self._filename))

    @property
    def _remote_dict(self):
        with fasteners.InterProcessLock(self._lockfile, logger=logger):
            remotes, _, _ = self._load()
            ret = OrderedDict([(ref, Remote(ref, remote_name, verify_ssl))
                               for ref, (remote_name, verify_ssl) in remotes.items()])
            return ret

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

    def __init__(self, filename, output):
        self._filename = filename
        self._lockfile = filename + ".lock"
        self._output = output

    @property
    def remotes(self):
        return _RemotesRegistry(self._filename, self._lockfile, self._output)

    @property
    def refs(self):
        return _ReferencesRegistry(self._filename, self._lockfile, self._output)

    @property
    def prefs(self):
        return _PackageReferencesRegistry(self._filename, self._lockfile, self._output)
