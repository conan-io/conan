import json

from conans.client.tools.scm import Git
from conans.errors import ConanException


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


class SCM(object):
    def __init__(self, data, repo_folder):
        self._data = data
        self.repo_folder = repo_folder
        # Finally instance a repo
        self.repo = self._get_repo()

    def _get_repo(self):
        repo = {"git": Git(self.repo_folder, verify_ssl=self._data.verify_ssl,
                           username=self._data.username,
                           password=self._data.password)}.get(self._data.type)
        if not repo:
            raise ConanException("SCM not supported: %s" % self._data.type)
        return repo

    @property
    def excluded_files(self):
        return self.repo.excluded_files()

    def clone(self):
        return self.repo.clone(self._data.url)

    def checkout(self):
        return self.repo.checkout(self._data.revision, submodule=self._data.submodule)

    def get_remote_url(self):
        return self.repo.get_remote_url()

    def get_revision(self):
        return self.repo.get_revision()

    def get_repo_root(self):
        return self.repo.get_repo_root()
