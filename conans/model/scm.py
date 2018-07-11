import json
import sys
import re

from conans.client.tools.scm import Git, SVN
from conans.errors import ConanException
from conans.util.files import load, save
from conans.client.output import ConanOutput


class SCMData(object):

    def __init__(self, conanfile):
        data = getattr(conanfile, "scm", None)
        if data is not None and isinstance(data, dict):
            self.type = data.get("type")
            self.url = data.get("url")
            self.revision = data.get("revision")
            self.verify_ssl = data.get("verify_ssl")
            self.username = data.get("username")
            self.password = data.get("password")
            self.subfolder = data.get("subfolder", "")
            self.submodule = data.get("submodule")
        else:
            raise ConanException("Not SCM enabled in conanfile")

    @property
    def capture_origin(self):
        return self.url == "auto"

    @property
    def capture_revision(self):
        return self.revision == "auto"

    def __repr__(self):
        d = {"url": self.url, "revision": self.revision, "username": self.username,
             "password": self.password, "type": self.type, "verify_ssl": self.verify_ssl,
             "subfolder": self.subfolder, "submodule": self.submodule}
        d = {k: v for k, v in d.items() if v}
        return json.dumps(d, sort_keys=True)

    def replace_in_file(self, path):
        content = load(path)
        dumps = self.__repr__()
        dumps = ",\n          ".join(dumps.split(","))
        content = re.sub(r"scm\s*=\s*{[^}]*}", "scm = %s" % dumps, content)
        save(path, content)


class SCM(object):
    def __init__(self, data, repo_folder, output=None):
        self._data = data
        self.repo_folder = repo_folder
        # Finally instance a repo
        self.repo = self._get_repo()
        self.output = output or ConanOutput(sys.stdout, True)

    def _get_repo(self):
        repo_class = {"git": Git, "svn": SVN}.get(self._data.type)
        if not repo_class:
            raise ConanException("SCM not supported: %s" % self._data.type)

        return repo_class(folder=self.repo_folder, verify_ssl=self._data.verify_ssl,
                          username=self._data.username, password=self._data.password)

    @property
    def excluded_files(self):
        return self.repo.excluded_files()

    def clone(self):
        return self.repo.clone(self._data.url, submodule=self._data.submodule)

    def checkout(self):
        return self.repo.checkout(self._data.revision)

    def get_remote_url(self):
        return self.repo.get_remote_url()

    def get_revision(self):
        return self.repo.get_revision()
