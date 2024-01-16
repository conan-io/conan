import fnmatch
import json
import os
from urllib.parse import urlparse

from conan.api.model import Remote
from conan.api.output import ConanOutput
from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanApp

from conans.client.cmd.user import user_set, users_clean, users_list
from conans.errors import ConanException
from conans.util.files import save, load

CONAN_CENTER_REMOTE_NAME = "conancenter"


class RemotesAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api
        self._remotes_file = HomePaths(self.conan_api.cache_folder).remotes_path

    def list(self, pattern=None, only_enabled=True):
        """
        :param pattern: if None, all remotes will be listed
                        it can be a single value or a list of values
        :param only_enabled:
        :return:
        """
        remotes = _load(self._remotes_file)
        if only_enabled:
            remotes = [r for r in remotes if not r.disabled]
        if pattern:
            remotes = _filter(remotes, pattern, only_enabled)
        return remotes

    def disable(self, pattern):
        remotes = _load(self._remotes_file)
        disabled = _filter(remotes, pattern, only_enabled=False)
        if disabled:
            for r in disabled:
                r.disabled = True
            _save(self._remotes_file, remotes)
        return remotes

    def enable(self, pattern):
        remotes = _load(self._remotes_file)
        enabled = _filter(remotes, pattern, only_enabled=False)
        if enabled:
            for r in enabled:
                r.disabled = False
            _save(self._remotes_file, remotes)
        return remotes

    def get(self, remote_name):
        remotes = _load(self._remotes_file)
        try:
            return {r.name: r for r in remotes}[remote_name]
        except KeyError:
            raise ConanException(f"Remote '{remote_name}' doesn't exist")

    def add(self, remote: Remote, force=False, index=None):
        remotes = _load(self._remotes_file)
        _validate_url(remote.url)
        current = {r.name: r for r in remotes}.get(remote.name)
        if current:  # same name remote existing!
            if not force:
                raise ConanException(f"Remote '{remote.name}' already exists in remotes "
                                     "(use --force to continue)")
            ConanOutput().warning(f"Remote '{remote.name}' already exists in remotes")
            if current.url != remote.url:
                ConanOutput().warning("Updating existing remote with new url")

        _check_urls(remotes, remote.url, force, current)
        if index is None:  # append or replace in place
            d = {r.name: r for r in remotes}
            d[remote.name] = remote
            remotes = list(d.values())
        else:
            remotes = [r for r in remotes if r.name != remote.name]
            remotes.insert(index, remote)
        _save(self._remotes_file, remotes)

    def remove(self, pattern: str):
        remotes = _load(self._remotes_file)
        removed = _filter(remotes, pattern, only_enabled=False)
        remotes = [r for r in remotes if r not in removed]
        _save(self._remotes_file, remotes)
        app = ConanApp(self.conan_api)
        for remote in removed:
            users_clean(app.cache.localdb, remote.url)

    def update(self, remote_name, url=None, secure=None, disabled=None, index=None):
        remotes = _load(self._remotes_file)
        try:
            remote = {r.name: r for r in remotes}[remote_name]
        except KeyError:
            raise ConanException(f"Remote '{remote_name}' doesn't exist")
        if url is not None:
            _validate_url(url)
            _check_urls(remotes, url, force=False, current=remote)
            remote.url = url
        if secure is not None:
            remote.verify_ssl = secure
        if disabled is not None:
            remote.disabled = disabled

        if index is not None:
            remotes = [r for r in remotes if r.name != remote.name]
            remotes.insert(index, remote)
        _save(self._remotes_file, remotes)

    def rename(self, remote_name: str, new_name: str):
        remotes = _load(self._remotes_file)
        d = {r.name: r for r in remotes}
        if new_name in d:
            raise ConanException(f"Remote '{new_name}' already exists")
        try:
            d[remote_name].name = new_name
        except KeyError:
            raise ConanException(f"Remote '{remote_name}' doesn't exist")
        _save(self._remotes_file, remotes)

    def user_info(self, remote: Remote):
        app = ConanApp(self.conan_api)
        return users_list(app.cache.localdb, remotes=[remote])[0]

    def login(self, remote: Remote, username, password):
        app = ConanApp(self.conan_api)
        app.remote_manager.authenticate(remote, username, password)

    def logout(self, remote: Remote):
        app = ConanApp(self.conan_api)
        # The localdb only stores url + username + token, not remote name, so use URL as key
        users_clean(app.cache.localdb, remote.url)

    def user_set(self, remote: Remote, username):
        app = ConanApp(self.conan_api)
        return user_set(app.cache.localdb, username, remote)

    def auth(self, remote: Remote, with_user=False):
        app = ConanApp(self.conan_api)
        if with_user:
            user, token, _ = app.cache.localdb.get_login(remote.url)
            if not user:
                var_name = f"CONAN_LOGIN_USERNAME_{remote.name.upper()}"
                user = os.getenv(var_name, None) or os.getenv("CONAN_LOGIN_USERNAME", None)
            if not user:
                return
        app.remote_manager.check_credentials(remote)
        user, token, _ = app.cache.localdb.get_login(remote.url)
        return user


def _load(remotes_file):
    if not os.path.exists(remotes_file):
        remote = Remote(CONAN_CENTER_REMOTE_NAME, "https://center.conan.io", True, False)
        _save(remotes_file, [remote])
        return [remote]

    data = json.loads(load(remotes_file))
    result = []
    for r in data.get("remotes", []):
        remote = Remote(r["name"], r["url"], r["verify_ssl"], r.get("disabled", False))
        result.append(remote)
    return result


def _save(remotes_file, remotes):
    remote_list = []
    for r in remotes:
        remote = {"name": r.name, "url": r.url, "verify_ssl": r.verify_ssl}
        if r.disabled:
            remote["disabled"] = True
        remote_list.append(remote)
    save(remotes_file, json.dumps({"remotes": remote_list}, indent=True))


def _filter(remotes, pattern, only_enabled=True):
    filtered_remotes = []
    patterns = [pattern] if isinstance(pattern, str) else pattern
    for p in patterns:
        is_match = False
        for remote in remotes:
            if fnmatch.fnmatch(remote.name, p):
                is_match = True
                if remote not in filtered_remotes:
                    filtered_remotes.append(remote)
        if not is_match:
            if "*" in p or "?" in p:
                if only_enabled:
                    raise ConanException(
                        f"Remotes for pattern '{p}' can't be found or are disabled")
            else:
                raise ConanException(f"Remote '{p}' can't be found or is disabled")
    return filtered_remotes


def _validate_url(url):
    """ Check if URL contains protocol and address
    :param url: URL to be validated
    """
    out = ConanOutput()
    if url:
        if url.startswith("https://conan.io/center"):
            raise ConanException("Wrong ConanCenter remote URL. You are adding the web "
                                 "https://conan.io/center the correct remote API is "
                                 "https://center.conan.io")
        address = urlparse(url)
        if not all([address.scheme, address.netloc]):
            out.warning(f"The URL '{url}' is invalid. It must contain scheme and hostname.")
    else:
        out.warning("The URL is empty. It must contain scheme and hostname.")


def _check_urls(remotes, url, force, current):
    # The remote name doesn't exist
    for r in remotes:
        if r is not current and r.url == url:
            msg = f"Remote url already existing in remote '{r.name}'. " \
                  f"Having different remotes with same URL is not recommended."
            if not force:
                raise ConanException(msg + " Use '--force' to override.")
            else:
                ConanOutput().warning(msg + " Adding duplicated remote url because '--force'.")
