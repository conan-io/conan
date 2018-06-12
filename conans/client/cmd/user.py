from conans.errors import ConanException
from conans.client.store.localdb import LocalDB


def users_list(client_cache, registry, remote_name):
    # List all users from required remotes
    remotes = [registry.remote(remote_name)] if remote_name else registry.remotes

    if not remotes:
        raise ConanException("No remotes defined")

    localdb = LocalDB(client_cache.localdb)
    ret = {"users": []}
    for remote in remotes:
        user_info = {}
        user, token = localdb.get_login(remote.url)
        user_info["remote_name"] = remote.name
        user_info["name"] = user
        user_info["authenticated"] = True if token else False
        ret["users"].append(user_info)
    return ret


def users_clean(client_cache):
    localdb = LocalDB(client_cache.localdb)
    localdb.init(clean=True)


def user_set(client_cache, registry, user, remote_name=None):
    localdb = LocalDB(client_cache.localdb)
    if not remote_name:
        remote = registry.default_remote
    else:
        remote = registry.remote(remote_name)

    if user.lower() == "none":
        user = None
    return update_localdb(localdb, user, None, remote)


def update_localdb(localdb, user, token, remote):
    previous_user = localdb.get_username(remote.url)
    localdb.set_login((user, token), remote.url)
    return remote.name, previous_user, user
