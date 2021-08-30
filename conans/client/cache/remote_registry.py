import fnmatch
import json
import os
import stat
from collections import OrderedDict, namedtuple
from six.moves.urllib.parse import urlparse

from conans.errors import ConanException, NoRemoteAvailable
from conans.util.config_parser import get_bool_from_text_value
from conans.util.files import load, save
from conans.model.ref import PackageReference, ConanFileReference


CONAN_CENTER_REMOTE_NAME = "conancenter"

Remote = namedtuple("Remote", "name url verify_ssl disabled")


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


def load_old_registry_json(contents):
    """From json"""
    data = json.loads(contents)
    remotes = Remotes()
    refs = data.get("references", {})
    prefs = data.get("package_references", {})
    for r in data["remotes"]:
        remotes.add(r["name"], r["url"], r["verify_ssl"])
    return remotes, refs, prefs


def migrate_registry_file(cache, out):
    folder = cache.cache_folder
    reg_json_path = os.path.join(folder, "registry.json")
    reg_txt_path = os.path.join(folder, "registry.txt")
    remotes_path = cache.remotes_path

    def add_ref_remote(reference, remotes_, remote_name_):
        ref_ = ConanFileReference.loads(reference, validate=True)
        remote = remotes_.get(remote_name_)
        if remote:
            with cache.package_layout(ref_).update_metadata() as metadata:
                metadata.recipe.remote = remote.name

    def add_pref_remote(pkg_ref, remotes_, remote_name_):
        pref_ = PackageReference.loads(pkg_ref, validate=True)
        remote = remotes_.get(remote_name_)
        if remote:
            with cache.package_layout(pref_.ref).update_metadata() as metadata:
                metadata.packages[pref_.id].remote = remote.name

    try:
        if os.path.exists(reg_json_path):
            out.warn("registry.json has been deprecated. Migrating to remotes.json")
            remotes, refs, prefs = load_old_registry_json(load(reg_json_path))
            remotes.save(remotes_path)
            for ref, remote_name in refs.items():
                add_ref_remote(ref, remotes, remote_name)
            for pref, remote_name in prefs.items():
                add_pref_remote(pref, remotes, remote_name)
            os.remove(reg_json_path)
        elif os.path.exists(reg_txt_path):
            out.warn("registry.txt has been deprecated. Migrating to remotes.json")
            remotes, refs = load_registry_txt(load(reg_txt_path))
            remotes.save(remotes_path)
            for ref, remote_name in refs.items():
                add_ref_remote(ref, remotes, remote_name)
            os.remove(reg_txt_path)

    except Exception as e:
        raise ConanException("Cannot migrate old registry: %s" % str(e))


class Remotes(object):
    def __init__(self):
        self._remotes = OrderedDict()
        self.selected = None

    @classmethod
    def defaults(cls):
        result = Remotes()
        result._remotes[CONAN_CENTER_REMOTE_NAME] = Remote(CONAN_CENTER_REMOTE_NAME,
                                                           "https://center.conan.io", True, False)
        return result

    def select(self, remote_name):
        self.selected = self[remote_name] if remote_name is not None else None

    def __bool__(self):
        return bool(self._remotes)

    def __nonzero__(self):
        return self.__bool__()

    def clear(self):
        self._remotes.clear()

    def items(self):
        return OrderedDict(
            (key, value) for (key, value) in self._remotes.items() if not value.disabled)

    def values(self):
        return [value for value in self._remotes.values() if not value.disabled]

    def all_values(self):
        return self._remotes.values()

    def all_items(self):
        return self._remotes.items()

    @staticmethod
    def loads(text):
        result = Remotes()
        data = json.loads(text)
        for r in data.get("remotes", []):
            disabled = r.get("disabled", False)
            result._remotes[r["name"]] = Remote(r["name"], r["url"],
                                                r["verify_ssl"], disabled)

        return result

    def dumps(self):
        result = []
        for remote in self._remotes.values():
            disabled_str = ", Disabled: True" if remote.disabled else ""
            result.append("%s: %s [Verify SSL: %s%s]" %
                          (remote.name, remote.url, remote.verify_ssl, disabled_str))
        return "\n".join(result)

    def save(self, filename):
        ret = {"remotes": []}
        for r, (_, u, v, d) in self._remotes.items():
            remote = {"name": r, "url": u, "verify_ssl": v}
            if d:
                remote["disabled"] = True
            ret["remotes"].append(remote)
        save(filename, json.dumps(ret, indent=True))

    def _get_by_url(self, url):
        for remote in self._remotes.values():
            if remote.url == url:
                return remote

    def rename(self, remote_name, new_remote_name):
        if new_remote_name in self._remotes:
            raise ConanException("Remote '%s' already exists" %
                                 new_remote_name)

        remote = self._remotes[remote_name]
        new_remote = Remote(new_remote_name, remote.url, remote.verify_ssl,
                            remote.disabled)
        self._remotes = OrderedDict([
            (new_remote_name, new_remote) if k == remote_name else (k, v)
            for k, v in self._remotes.items()
        ])

    def set_disabled_state(self, remote_name, state):
        filtered_remotes = []
        for remote in self._remotes.values():
            if fnmatch.fnmatch(remote.name, remote_name):
                filtered_remotes.append(remote)

        if not filtered_remotes and "*" not in remote_name:
            raise NoRemoteAvailable("Remote '%s' not found in remotes" % remote_name)

        for remote in filtered_remotes:
            if remote.disabled == state:
                continue
            self._remotes[remote.name] = Remote(remote.name, remote.url, remote.verify_ssl, state)

    def get_remote(self, remote_name):
        # Returns the remote defined by the name, or the default if is None
        return self[remote_name] if remote_name is not None else self.default

    @property
    def default(self):
        try:
            # This is the python way to get the first element of an OrderedDict
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
            raise NoRemoteAvailable("No remote '%s' defined in remotes" % remote_name)

    def __delitem__(self, remote_name):
        try:
            del self._remotes[remote_name]
        except KeyError:
            raise NoRemoteAvailable("No remote '%s' defined in remotes" % remote_name)

    def _upsert(self, remote_name, url, verify_ssl, insert):
        # Remove duplicates
        updated_remote = Remote(remote_name, url, verify_ssl, False)
        self._remotes.pop(remote_name, None)
        remotes_list = []
        renamed = None

        for name, remote in self._remotes.items():
            if remote.url != url:
                remotes_list.append((name, remote))
            else:
                renamed = name

        if insert is not None:
            try:
                insert_index = int(insert)
            except ValueError:
                raise ConanException("insert argument must be an integer")
            remotes_list.insert(insert_index, (remote_name, updated_remote))
        else:
            remotes_list.append((remote_name, updated_remote))
        self._remotes = OrderedDict(remotes_list)
        return renamed

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        if force:
            return self._upsert(remote_name, url, verify_ssl, insert)

        if remote_name in self._remotes:
            raise ConanException("Remote '%s' already exists in remotes (use update to modify)"
                                 % remote_name)
        self._add_update(remote_name, url, verify_ssl, insert)

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        if remote_name not in self._remotes:
            raise ConanException("Remote '%s' not found in remotes" % remote_name)
        self._add_update(remote_name, url, verify_ssl, insert)

    def _add_update(self, remote_name, url, verify_ssl, insert=None):
        prev_remote = self._get_by_url(url)
        if prev_remote and verify_ssl == prev_remote.verify_ssl and insert is None:
            raise ConanException("Remote '%s' already exists with same URL" % prev_remote.name)
        disabled = True if prev_remote and prev_remote.disabled else False
        updated_remote = Remote(remote_name, url, verify_ssl, disabled)
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

    def __init__(self, cache, output):
        self._cache = cache
        self._output = output
        self._filename = cache.remotes_path

    def _validate_url(self, url):
        """ Check if URL contains protocol and address

        :param url: URL to be validated
        """
        if url:
            address = urlparse(url)
            if not all([address.scheme, address.netloc]):
                self._output.warn("The URL '%s' is invalid. It must contain scheme and hostname."
                                  % url)
        else:
            self._output.warn("The URL is empty. It must contain scheme and hostname.")

    def initialize_remotes(self):
        if not os.path.exists(self._filename):
            self._output.warn("Remotes registry file missing, "
                              "creating default one in %s" % self._filename)
            remotes = Remotes.defaults()
            remotes.save(self._filename)

    def reset_remotes(self):
        if os.path.exists(self._filename):
            os.chmod(self._filename, stat.S_IWRITE)
            os.remove(self._filename)
        self.initialize_remotes()

    def load_remotes(self):
        self.initialize_remotes()
        content = load(self._filename)
        return Remotes.loads(content)

    def add(self, remote_name, url, verify_ssl=True, insert=None, force=None):
        self._validate_url(url)
        remotes = self.load_remotes()
        renamed = remotes.add(remote_name, url, verify_ssl, insert, force)
        remotes.save(self._filename)
        if renamed:
            with self._cache.editable_packages.disable_editables():
                for ref in self._cache.all_refs():
                    with self._cache.package_layout(ref).update_metadata() as metadata:
                        if metadata.recipe.remote == renamed:
                            metadata.recipe.remote = remote_name
                        for pkg_metadata in metadata.packages.values():
                            if pkg_metadata.remote == renamed:
                                pkg_metadata.remote = remote_name

    def update(self, remote_name, url, verify_ssl=True, insert=None):
        self._validate_url(url)
        remotes = self.load_remotes()
        remotes.update(remote_name, url, verify_ssl, insert)
        remotes.save(self._filename)

    def clear(self):
        remotes = self.load_remotes()
        remotes.clear()
        with self._cache.editable_packages.disable_editables():
            for ref in self._cache.all_refs():
                with self._cache.package_layout(ref).update_metadata() as metadata:
                    metadata.recipe.remote = None
                    for pkg_metadata in metadata.packages.values():
                        pkg_metadata.remote = None
            remotes.save(self._filename)

    def remove(self, remote_name):
        remotes = self.load_remotes()
        del remotes[remote_name]
        with self._cache.editable_packages.disable_editables():
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
        with self._cache.editable_packages.disable_editables():
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
        with self._cache.editable_packages.disable_editables():
            for ref in self._cache.all_refs():
                with self._cache.package_layout(ref).update_metadata() as metadata:
                    if metadata.recipe.remote == remote_name:
                        metadata.recipe.remote = new_remote_name
                    for pkg_metadata in metadata.packages.values():
                        if pkg_metadata.remote == remote_name:
                            pkg_metadata.remote = new_remote_name

            remotes.save(self._filename)

    def set_disabled_state(self, remote_name, state):
        remotes = self.load_remotes()
        remotes.set_disabled_state(remote_name, state)
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
