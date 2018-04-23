from conans.errors import ConanException
from conans.client.store.localdb import LocalDB


def users_list(client_cache, registry, remote_name=None):
    # List all users from required remotes
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


def user_set(client_cache, output, registry, user, remote_name=None):
    localdb = LocalDB(client_cache.localdb)
    if not remote_name:
        remote = registry.default_remote
    else:
        remote = registry.remote(remote_name)

    if user.lower() == "none":
        user = None
    update_localdb(localdb, user, None, remote, output)


def update_localdb(localdb, user, token, remote, output):
    previous_user = localdb.get_username(remote.url)
    localdb.set_login((user, token), remote.url)
    previous_user = previous_user or "None (anonymous)"
    user = user or "None (anonymous)"
    if previous_user == user:
        output.info("Current '%s' user already: %s" % (remote.name, previous_user))
    else:
        output.info("Change '%s' user from %s to %s" % (remote.name, previous_user, user))
