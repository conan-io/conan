import json
import os

from conans.client.tools.scm import Git, SVN
from conans.errors import ConanException


def get_scm_data(conanfile):
    try:
        return SCMData(conanfile)
    except ConanException:
        return None


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

    @property
    def recipe_revision(self):
        if self.type in ["git", "svn"]:
            return self.revision
        raise ConanException("Not implemented recipe revision for %s" % self.type)

    def __repr__(self):
        d = {"url": self.url, "revision": self.revision, "username": self.username,
             "password": self.password, "type": self.type, "verify_ssl": self.verify_ssl,
             "subfolder": self.subfolder, "submodule": self.submodule}
        d = {k: v for k, v in d.items() if v}
        return json.dumps(d, sort_keys=True)


class SCM(object):
    availables = {'git': Git, 'svn': SVN}

    def __init__(self, data, repo_folder, output):
        self._data = data
        self._output = output
        self.repo_folder = repo_folder
        # Finally instance a repo
        self.repo = self._get_repo()

    @classmethod
    def detect_scm(cls, folder):
        for name, candidate in cls.availables.items():
            try:
                candidate(folder).check_repo()
                return name
            except ConanException:
                pass
        return None

    def _get_repo(self):
        repo_class = self.availables.get(self._data.type)
        if not repo_class:
            raise ConanException("SCM not supported: %s" % self._data.type)

        return repo_class(folder=self.repo_folder, verify_ssl=self._data.verify_ssl,
                          username=self._data.username, password=self._data.password,
                          output=self._output)

    @property
    def excluded_files(self):
        return self.repo.excluded_files()

    def checkout(self):
        output = ""
        if self._data.type == "git":
            output += self.repo.clone(url=self._data.url)
            output += self.repo.checkout(element=self._data.revision,
                                         submodule=self._data.submodule)
        else:
            output += self.repo.checkout(url=self._data.url, revision=self._data.revision)
        return output

    def get_remote_url(self, remove_credentials):
        return self.repo.get_remote_url(remove_credentials=remove_credentials)

    def get_revision(self):
        return self.repo.get_revision()

    def is_pristine(self):
        return self.repo.is_pristine()

    def get_repo_root(self):
        return self.repo.get_repo_root()

    def get_qualified_remote_url(self, remove_credentials):
        if self._data.type == "git":
            return self.repo.get_remote_url(remove_credentials=remove_credentials)
        else:
            return self.repo.get_qualified_remote_url(remove_credentials=remove_credentials)

    def is_local_repository(self):
        return self.repo.is_local_repository()

    @staticmethod
    def clean_url(url):
        _, last_chunk = url.rsplit('/', 1)
        if '@' in last_chunk:  # Remove peg_revision
            url, peg_revision = url.rsplit('@', 1)
            return url
        return url

    def get_local_path_to_url(self, url):
        """ Compute the local path to the directory where the URL is pointing to (only make sense
            for CVS where chunks of the repository can be checked out isolated). The argument
            'url' should be contained inside the root url.
        """
        src_root = self.get_repo_root()

        if self._data.type == "git":
            return src_root

        url_root = SCM(self._data, src_root, self._output).get_remote_url(remove_credentials=True)
        if url_root:
            url = self.clean_url(url)
            src_path = os.path.join(src_root, os.path.relpath(url, url_root))
            return src_path
