from conans.client.remote_registry import RemoteRegistry
from conans.errors import ConanException
from conans.client.store.localdb import LocalDB


def users_list(client_cache, output, remote_name=None):
    # List all users from required remotes
    registry = RemoteRegistry(client_cache.registry, output)
    if remote_name:
        remotes = [registry.remote(remote_name)]
    else:
        remotes = registry.remotes

    if not remotes:
        raise ConanException("No remotes defined")

    localdb = LocalDB(client_cache.localdb)
    result = []
    for remote in remotes:
        prev_user = localdb.get_username(remote.url)
        username = prev_user or "None (anonymous)"
        result.append((remote.name, username))
    return result


def users_clean(client_cache):
    localdb = LocalDB(client_cache.localdb)
    localdb.init(clean=True)


def set_user(client_cache, output, username, remote=None):
    localdb = LocalDB(client_cache.localdb)
    registry = RemoteRegistry(client_cache.registry, output)

    remote_url = self._remote.url
    prev_user = localdb.get_username(remote_url)

    if user is None:
        if prev_user is None:
            raise ConanException("User for remote '%s' is not defined" % self._remote.name)
        user = prev_user
    elif user.lower() == "none":
        user = None

    # Perform auth if user, pass defined
        token = None
    # Store result in DB
    localdb.set_login((user, token), remote_url)
    # Output
    prev_user = prev_user or "None (anonymous)"
    user = user or "None (anonymous)"
    if prev_user == user:
        self._user_io.out.info("Current '%s' user already: %s"
                               % (self._remote.name, prev_user))
    else:
        self._user_io.out.info("Change '%s' user from %s to %s"
                               % (self._remote.name, prev_user, user))
    return token


