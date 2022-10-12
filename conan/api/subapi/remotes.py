import fnmatch

from conan.api.subapi import api_method
from conan.api.conan_app import ConanApp
from conans.client.cache.remote_registry import Remote
from conans.client.cmd.user import user_set, users_clean, users_list
from conans.errors import ConanException


# TODO: Redesign these, why not part of the API?
#  Why selection logic is different for "conan list" and "conan install"
def get_remote_selection(conan_api, remote_patterns):
    """
    Return a list of Remote() objects matching the specified patterns. If a pattern doesn't match
    anything, it fails
    """
    ret_remotes = []
    for pattern in remote_patterns:
        tmp = conan_api.remotes.list(pattern=pattern, only_active=True)
        if not tmp:
            raise ConanException("Remotes for pattern '{}' can't be found or are "
                                 "disabled".format(pattern))
        ret_remotes.extend(tmp)
    return ret_remotes


def get_multiple_remotes(conan_api, remote_names=None):
    if remote_names:
        # FIXME: Check this, this can get disabled remotes, it is intended?
        return [conan_api.remotes.get(remote_name) for remote_name in remote_names]
    elif remote_names is None:
        # if we don't pass any remotes we want to retrieve only the enabled ones
        return conan_api.remotes.list(only_active=True)


class RemotesAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def list(self, pattern=None, only_active=False):
        app = ConanApp(self.conan_api.cache_folder)
        remotes = app.cache.remotes_registry.list()
        if only_active:
            remotes = [r for r in remotes if not r.disabled]
        if pattern:
            filtered_remotes = []
            for remote in remotes:
                if fnmatch.fnmatch(remote.name, pattern):
                    filtered_remotes.append(remote)

            if not filtered_remotes and "*" not in pattern:
                raise ConanException(f"Remote '{pattern}' not found in remotes")

            remotes = filtered_remotes
        return remotes

    @api_method
    def get(self, remote_name):
        app = ConanApp(self.conan_api.cache_folder)
        return app.cache.remotes_registry.read(remote_name)

    @api_method
    def add(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.add(remote)

    @api_method
    def remove(self, remote_name):
        app = ConanApp(self.conan_api.cache_folder)
        remote = app.cache.remotes_registry.remove(remote_name)
        users_clean(app.cache.localdb, remote.url)

    @api_method
    def update(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.update(remote)

    @api_method
    def move(self, remote: Remote, index: int):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.move(remote, index)

    @api_method
    def rename(self, remote: Remote, new_name: str):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.rename(remote, new_name)

    @api_method
    def user_info(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        return users_list(app.cache.localdb, remotes=[remote])[0]

    @api_method
    def login(self, remote: Remote, username, password):
        app = ConanApp(self.conan_api.cache_folder)
        app.remote_manager.authenticate(remote, username, password)

    @api_method
    def logout(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        # The localdb only stores url + username + token, not remote name, so use URL as key
        users_clean(app.cache.localdb, remote.url)

    @api_method
    def user_set(self, remote: Remote, username):
        app = ConanApp(self.conan_api.cache_folder)
        return user_set(app.cache.localdb, username, remote)
