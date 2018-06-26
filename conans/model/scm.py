import json
import os

from conans.client.tools.scm import Git
from conans.errors import ConanException
from conans.util.files import load, save
import re


class SCM(object):

    def __init__(self, data, src_folder):
        self.type = data.get("type")
        self.url = data.get("url")
        self.revision = data.get("revision")
        self.verify_ssl = data.get("verify_ssl")
        self.subfolder = data.get("subfolder")
        if data.get("subfolder"):
            self.src_folder = os.path.join(src_folder, self.subfolder)
        else:
            self.src_folder = src_folder

        self.username = data.get("username")
        self.password = data.get("password")

        # Finally instance a repo
        self.repo = self._get_repo()

    def _get_repo(self):
        repo = {"git": Git(self.src_folder, verify_ssl=self.verify_ssl,
                           username=self.username, password=self.password)}.get(self.type)
        if not repo:
            raise ConanException("SCM not supported: %s" % self.type)
        return repo

    @property
    def capture_origin(self):
        return self.url == "auto"

    @property
    def capture_revision(self):
        return self.revision == "auto"

    def clone(self):
        return self.repo.clone(self.url)

    def checkout(self):
        return self.repo.checkout(self.revision)

    def get_remote_url(self):
        return self.repo.get_remote_url()

    def get_revision(self):
        return self.repo.get_revision()

    def __repr__(self):
        d = {"url": self.url, "revision": self.revision, "username": self.username,
             "password": self.password, "type": self.type, "verify_ssl": self.verify_ssl,
             "subfolder": self.subfolder}
        d = {k: v for k, v in d.items() if v}
        return json.dumps(d, sort_keys=True)

    def replace_in_file(self, path):
        content = load(path)
        dumps = self.__repr__()
        dumps = ",\n          ".join(dumps.split(","))
        content = re.sub(r"scm\s*=\s*{[^}]*}", "scm = %s" % dumps, content)
        save(path, content)
