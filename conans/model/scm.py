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
        self.ssl_verify = data.get("ssl_verify")
        self.subfolder = data.get("subfolder")
        if data.get("subfolder"):
            self.src_folder = os.path.join(src_folder, self.subfolder)
        else:
            self.src_folder = src_folder

        self.auth_env = data.get("auth_env")

        # Finally instance a repo
        self.repo = self._get_repo()

    def _get_repo(self):
        repo = {"git": Git(self.ssl_verify, self.auth_env)}.get(self.type)
        if not repo:
            raise ConanException("SCM not supported: %s" % self.type)
        return repo

    @property
    def capture_enabled(self):
        return self.url == "auto" or self.revision == "auto"

    def clone(self):
        return self.repo.clone(self.url, self.src_folder)

    def checkout(self):
        return self.repo.checkout(self.revision, self.src_folder)

    def get_repo_url(self):
        return self.repo.get_remote_url(self.src_folder)

    def get_repo_revision(self):
        return self.repo.get_revision(self.src_folder)

    def __repr__(self):
        d = {"url": self.url, "revision": self.revision, "auth_env": self.auth_env,
             "type": self.type, "ssl_verify": self.ssl_verify, "subfolder": self.subfolder}
        d = {k: v for k, v in d.items() if v}
        return json.dumps(d)

    def replace_in_file(self, path):
        content = load(path)
        dumps = self.__repr__()
        dumps = ",\n          ".join(dumps.split(","))
        content = re.sub(r"scm\s*=\s*{[^}]*}", "scm = %s" % dumps, content)
        save(path, content)
