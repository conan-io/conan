import fnmatch

from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.cache.remote_registry import Remote
from conans.client.cmd.user import user_set, users_clean, users_list
from conans.errors import ConanException


class RemotesAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def list(self, filter=None, only_active=False):
        app = ConanApp(self.conan_api.cache_folder)
        remotes = app.cache.remotes_registry.list()
        if filter:
            filtered_remotes = []
            for remote in remotes:
                if fnmatch.fnmatch(remote.name, filter):
                    filtered_remotes.append(remote)

            if not filtered_remotes and "*" not in filter:
                raise ConanException("Remote '%s' not found in remotes" % filter)

            remotes = filtered_remotes
        if only_active:
            remotes = [r for r in remotes if not r.disabled]
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
    def remove(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.remove(remote)

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
