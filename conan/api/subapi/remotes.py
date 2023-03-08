import fnmatch
import os

from conan.internal.conan_app import ConanApp
from conans.client.cache.remote_registry import Remote
from conans.client.cmd.user import user_set, users_clean, users_list
from conans.errors import ConanException


class RemotesAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def list(self, pattern=None, only_enabled=True):
        """
        :param pattern: if None, all remotes will be listed
                        it can be a single value or a list of values
        :param only_enabled:
        :return:
        """
        app = ConanApp(self.conan_api.cache_folder)
        remotes = app.cache.remotes_registry.list()
        if only_enabled:
            remotes = [r for r in remotes if not r.disabled]
        if pattern:
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

            remotes = filtered_remotes
        return remotes

    def disable(self, pattern):
        remotes = self.list(pattern, only_enabled=False)
        for r in remotes:
            r.disabled = True
            self.update(r)
        return remotes

    def enable(self, pattern):
        remotes = self.list(pattern, only_enabled=False)
        for r in remotes:
            r.disabled = False
            self.update(r)
        return remotes

    def get(self, remote_name):
        app = ConanApp(self.conan_api.cache_folder)
        return app.cache.remotes_registry.read(remote_name)

    def add(self, remote: Remote, force=False):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.add(remote, force=force)

    def remove(self, remote_name):
        app = ConanApp(self.conan_api.cache_folder)
        remotes = self.list(remote_name, only_enabled=False)
        for remote in remotes:
            app.cache.remotes_registry.remove(remote.name)
            users_clean(app.cache.localdb, remote.url)

    def update(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.update(remote)

    def move(self, remote: Remote, index: int):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.move(remote, index)

    def rename(self, remote: Remote, new_name: str):
        app = ConanApp(self.conan_api.cache_folder)
        app.cache.remotes_registry.rename(remote, new_name)

    def user_info(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        return users_list(app.cache.localdb, remotes=[remote])[0]

    def login(self, remote: Remote, username, password):
        app = ConanApp(self.conan_api.cache_folder)
        app.remote_manager.authenticate(remote, username, password)

    def logout(self, remote: Remote):
        app = ConanApp(self.conan_api.cache_folder)
        # The localdb only stores url + username + token, not remote name, so use URL as key
        users_clean(app.cache.localdb, remote.url)

    def user_set(self, remote: Remote, username):
        app = ConanApp(self.conan_api.cache_folder)
        return user_set(app.cache.localdb, username, remote)

    def auth(self, remote: Remote, with_user=False):
        app = ConanApp(self.conan_api.cache_folder)
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
