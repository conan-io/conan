import os
import subprocess

from six import string_types

from conans.client.tools.scm import Git, SVN
from conans.errors import ConanException
from conans.util.files import rmdir


def get_scm_data(conanfile):
    data = getattr(conanfile, "scm", None)
    if data is not None and isinstance(data, dict):
        return SCMData(conanfile)
    else:
        return None


def _get_dict_value(data, key, expected_type, default=None, disallowed_type=None):
    if key in data:
        r = data.get(key)
        if r is None:  # None is always a valid value
            return r
        if not isinstance(r, expected_type) or (disallowed_type and isinstance(r, disallowed_type)):
            type_str = "' or '".join([it.__name__ for it in expected_type]) \
                if isinstance(expected_type, tuple) else expected_type.__name__
            raise ConanException("SCM value for '{}' must be of type '{}'"
                                 " (found '{}')".format(key, type_str, type(r).__name__))
        return r
    return default


class SCMData(object):
    VERIFY_SSL_DEFAULT = True
    SHALLOW_DEFAULT = True

    def __init__(self, conanfile):
        data = getattr(conanfile, "scm")
        self.type = _get_dict_value(data, "type", string_types)
        self.url = _get_dict_value(data, "url", string_types)
        self.revision = _get_dict_value(data, "revision", string_types + (int,),
                                        disallowed_type=bool)  # bool is subclass of integer
        self.verify_ssl = _get_dict_value(data, "verify_ssl", bool, SCMData.VERIFY_SSL_DEFAULT)
        self.username = _get_dict_value(data, "username", string_types)
        self.password = _get_dict_value(data, "password", string_types)
        self.subfolder = _get_dict_value(data, "subfolder", string_types)
        self.submodule = _get_dict_value(data, "submodule", string_types)
        self.shallow = _get_dict_value(data, "shallow", bool, SCMData.SHALLOW_DEFAULT)

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

    def as_dict(self):
        d = {"url": self.url, "revision": self.revision, "username": self.username,
             "password": self.password, "type": self.type,
             "subfolder": self.subfolder, "submodule": self.submodule}
        d = {k: v for k, v in d.items() if v is not None}
        # Preserve the value 'None' for those entries with not falsy default.
        if self.shallow != self.SHALLOW_DEFAULT:
            d.update({"shallow": self.shallow})
        if self.verify_ssl != self.VERIFY_SSL_DEFAULT:
            d.update({"verify_ssl": self.verify_ssl})
        return d

    def __repr__(self):
        d = self.as_dict()

        def _kv_to_string(key, value):
            if isinstance(value, bool):
                return '"{}": {}'.format(key, value)
            elif value is None:
                return '"{}": None'.format(key)
            else:
                value_str = str(value).replace('"', r'\"')
                return '"{}": "{}"'.format(key, value_str)

        return '{' + ', '.join([_kv_to_string(k, v) for k, v in sorted(d.items())]) + '}'


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
            def use_not_shallow():
                out = self.repo.clone(url=self._data.url, shallow=False)
                out += self.repo.checkout(element=self._data.revision,
                                          submodule=self._data.submodule)
                return out

            def use_shallow():
                try:
                    out = self.repo.clone(url=self._data.url, branch=self._data.revision,
                                          shallow=True)
                except subprocess.CalledProcessError:
                    # remove the .git directory, otherwise, fallback clone cannot be successful
                    # it's completely safe to do here, as clone without branch expects
                    # empty directory
                    rmdir(os.path.join(self.repo_folder, ".git"))
                    out = use_not_shallow()
                else:
                    out += self.repo.checkout_submodules(submodule=self._data.submodule)
                return out

            if self._data.shallow:
                output += use_shallow()
            else:
                output += use_not_shallow()

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
