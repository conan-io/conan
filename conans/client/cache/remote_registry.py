import json
import os
from urllib.parse import urlparse

from conan.api.model import Remote
from conan.api.output import ConanOutput
from conans.errors import ConanException
from conans.util.files import load, save

CONAN_CENTER_REMOTE_NAME = "conancenter"


class _Remotes:
    """Class to manage an ordered list of Remote objects, performing validations
    and updating the remotes. Used by RemoteRegistry only! """

    def __init__(self):
        self._remotes = {}

    def __bool__(self):
        return bool(self._remotes)

    def __getitem__(self, remote_name):
        try:
            return self._remotes[remote_name]
        except KeyError:
            raise ConanException(f"Remote '{remote_name}' doesn't exist")

    @staticmethod
    def load(filename):
        text = load(filename)
        result = _Remotes()
        data = json.loads(text)
        for r in data.get("remotes", []):
            disabled = r.get("disabled", False)
            # TODO: Remote.serialize/deserialize
            remote = Remote(r["name"], r["url"], r["verify_ssl"], disabled)
            result._remotes[r["name"]] = remote
        return result

    def dumps(self):
        remote_list = []
        for r in self._remotes.values():
            remote = {"name": r.name, "url": r.url, "verify_ssl": r.verify_ssl}
            if r.disabled:
                remote["disabled"] = True
            remote_list.append(remote)
        ret = {"remotes": remote_list}
        return json.dumps(ret, indent=True)

    def rename(self, remote_name, new_remote_name):
        if new_remote_name in self._remotes:
            raise ConanException("Remote '%s' already exists" % new_remote_name)

        r = self[remote_name]
        r._name = new_remote_name
        # Keep the remotes order
        self._remotes = {r.name: r for r in self._remotes.values()}

    def remove(self, remote_name):
        try:
            self._remotes.pop(remote_name)
        except KeyError:
            raise ConanException(f"Remote '{remote_name}' doesn't exist")

    def add(self, new_remote: Remote, index=None, force=False):
        assert isinstance(new_remote, Remote)
        current = self._remotes.get(new_remote.name)
        if current:  # same name remote existing!
            if not force:
                raise ConanException(f"Remote '{new_remote.name}' already exists in remotes "
                                     "(use --force to continue)")

            ConanOutput().warning(f"Remote '{new_remote.name}' already exists in remotes")
            if current.url != new_remote.url:
                ConanOutput().warning("Updating existing remote with new url")
            current_index = self._remotes.index(current)
            self._remotes.remove(current)
            index = index or current_index
            self._remotes.insert(index, new_remote)
            return

        # The remote name doesn't exist
        for r in self._remotes:
            if r.url == new_remote.url:
                msg = f"Remote url already existing in remote '{r.name}'. " \
                      f"Having different remotes with same URL is not recommended."
                if not force:
                    raise ConanException(msg + " Use '--force' to override.")
                else:
                    ConanOutput().warning(msg + " Adding duplicated remote because '--force'.")
        if index:
            self._remotes.insert(index, new_remote)
        else:
            self._remotes.append(new_remote)

    def update(self, remote_name, url=None, secure=None, index=None):
        remote = self[remote_name]
        if url is not None:
            remote.url = url
        if secure is not None:
            remote.verify_ssl = secure

        self._remotes[remote.name] = remote

    def items(self):
        return list(self._remotes.values())


class RemoteRegistry(object):
    """Store remotes in disk and modify remotes for the 'conan remote' command.
    It never returns an _Remotes object, only Remote model"""

    def __init__(self, cache):
        self._output = ConanOutput()
        self._filename = cache.remotes_path

    def _validate_url(self, url):
        """ Check if URL contains protocol and address

        :param url: URL to be validated
        """
        if url:
            address = urlparse(url)
            if not all([address.scheme, address.netloc]):
                self._output.warning("The URL '%s' is invalid. It must contain scheme and hostname."
                                     % url)
        else:
            self._output.warning("The URL is empty. It must contain scheme and hostname.")

    def initialize_remotes(self):
        if not os.path.exists(self._filename):
            remotes = _Remotes()
            remote = Remote(CONAN_CENTER_REMOTE_NAME, "https://center.conan.io", True, False)
            remotes.add(remote)
            self.save_remotes(remotes)

    def _load_remotes(self):
        self.initialize_remotes()
        return _Remotes.load(self._filename)

    def list(self):
        return self._load_remotes().items()

    def read(self, remote_name):
        remotes = self._load_remotes()
        ret = remotes[remote_name]
        return ret

    def get_remote_index(self, remote: Remote):
        try:
            return self.list().index(remote)
        except ValueError:
            raise ConanException("No remote: '{}' found".format(remote.name))

    def add(self, remote: Remote, force=False, index=None):
        self._validate_url(remote.url)
        remotes = self._load_remotes()
        remotes.add(remote, force=force, index=index)
        self.save_remotes(remotes)

    def remove(self, remote_name):
        assert isinstance(remote_name, str)
        remotes = self._load_remotes()
        remotes.remove(remote_name)
        self.save_remotes(remotes)

    def update(self, remote):
        self._validate_url(remote.url)
        remotes = self._load_remotes()
        remotes.update(remote)
        self.save_remotes(remotes)

    def move(self, remote, index):
        remotes = self._load_remotes()
        remotes.move(remote, new_index=index)
        self.save_remotes(remotes)

    def rename(self, remote, new_name):
        remotes = self._load_remotes()
        remotes.rename(remote, new_name)
        self.save_remotes(remotes)

    def save_remotes(self, remotes):
        save(self._filename, remotes.dumps())
