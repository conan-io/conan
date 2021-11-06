import json
import os
from urllib.parse import urlparse

import stat

from conans.cli.api.model import Remote
from conans.cli.output import ConanOutput
from conans.errors import ConanException, NoRemoteAvailable
from conans.util.config_parser import get_bool_from_text_value
from conans.util.files import load, save

CONAN_CENTER_REMOTE_NAME = "conancenter"


def load_registry_txt(contents):
    """Remove in Conan 2.0"""
    remotes = _Remotes()
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
            remotes.add(Remote(remote_name, url, verify_ssl, False))
        else:
            ref, remote_name = chunks
            refs[ref] = remote_name

    return remotes, refs


class _Remotes(object):
    """Class to manage an ordered list of Remote objects, performing validations
    and updating the remotes. Used by RemoteRegistry only! """

    def __init__(self):
        self._remotes = []

    def __bool__(self):
        return bool(self._remotes)

    def rename(self, remote, new_remote_name):
        if self.get_by_name(new_remote_name):
            raise ConanException("Remote '%s' already exists" % new_remote_name)

        r = self.get_by_name(remote.name)
        r._name = new_remote_name
        remote._name = new_remote_name

    @property
    def default(self):
        ret = self._remotes[0]
        if not ret:
            raise NoRemoteAvailable("No default remote defined")
        return ret

    def remove(self, remote_name):
        r = self.get_by_name(remote_name)
        if r is None:
            raise ConanException("The specified remote doesn't exist")
        index = self._remotes.index(r)
        return self._remotes.pop(index)

    def add(self, new_remote: Remote, index=None):
        assert isinstance(new_remote, Remote)
        current = self.get_by_name(new_remote.name)
        if current:
            raise ConanException("Remote '%s' already exists in remotes (use update to modify)"
                                 % new_remote.name)
        if index:
            self._remotes.insert(index, new_remote)
        else:
            self._remotes.append(new_remote)

    def update(self, remote: Remote):
        assert isinstance(remote, Remote)
        current = self.get_by_name(remote.name)
        if not current:
            raise ConanException("The remote '{}' doesn't exist".format(remote.name))

        index = self._remotes.index(current)
        self._remotes.remove(current)
        self._remotes.insert(index, remote)

    def move(self, remote: Remote, new_index: int):
        assert isinstance(remote, Remote)
        self.remove(remote.name)
        self._remotes.insert(new_index, remote)

    def get_by_name(self, name):
        for r in self._remotes:
            if r.name == name:
                return r
        return None

    def items(self):
        return self._remotes


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
            self._output.warning("Remotes registry file missing, "
                                 "creating default one in %s" % self._filename)
            remotes = _Remotes()
            remote = Remote(CONAN_CENTER_REMOTE_NAME, "https://center.conan.io", True, False)
            remotes.add(remote)
            self.save_remotes(remotes)

    def reset_remotes(self):
        if os.path.exists(self._filename):
            os.chmod(self._filename, stat.S_IWRITE)
            os.remove(self._filename)
        self.initialize_remotes()

    def _load_remotes(self):
        self.initialize_remotes()
        content = load(self._filename)
        result = _Remotes()
        data = json.loads(content)
        for r in data.get("remotes", []):
            disabled = r.get("disabled", False)
            remote = Remote(r["name"], r["url"], r["verify_ssl"], disabled)
            result._remotes.append(remote)
        return result

    @staticmethod
    def _dumps_json(remotes):
        ret = {"remotes": []}
        for r in remotes.items():
            remote = {"name": r.name, "url": r.url, "verify_ssl": r.verify_ssl}
            if r.disabled:
                remote["disabled"] = True
            ret["remotes"].append(remote)
        return json.dumps(ret, indent=True)

    def list(self):
        return self._load_remotes().items()

    @property
    def default(self):
        return self.list()[0]

    def read(self, remote_name):
        remotes = self._load_remotes()
        ret = remotes.get_by_name(remote_name)
        if not ret:
            raise ConanException("Remote '%s' not found in remotes" % remote_name)
        return ret

    def add(self, remote: Remote):
        self._validate_url(remote.url)
        remotes = self._load_remotes()
        remotes.add(remote)
        self.save_remotes(remotes)

    def remove(self, remote_name):
        assert isinstance(remote_name, str)
        remotes = self._load_remotes()
        remote = remotes.remove(remote_name)
        self.save_remotes(remotes)
        return remote

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
        save(self._filename, self._dumps_json(remotes))
