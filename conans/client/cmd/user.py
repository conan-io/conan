from conans.errors import ConanException
from conans.client.store.localdb import LocalDB


def users_list(localdb_file, remotes):
    if not remotes:
        raise ConanException("No remotes defined")

    localdb = LocalDB(localdb_file)
    remotes_info = []
    for remote in remotes:
        user_info = {}
        user, token = localdb.get_login(remote.url)
        user_info["name"] = remote.name
        user_info["user_name"] = user
        user_info["authenticated"] = True if token else False
        remotes_info.append(user_info)
    return remotes_info


def users_clean(localdb_file):
    localdb = LocalDB(localdb_file)
    localdb.init(clean=True)


def user_set(localdb_file, user, remote_name=None):
    localdb = LocalDB(localdb_file)

    if user.lower() == "none":
        user = None
    return update_localdb(localdb, user, None, remote_name)


def update_localdb(localdb, user, token, remote):
    previous_user = localdb.get_username(remote.url)
    localdb.set_login((user, token), remote.url)
    return remote.name, previous_user, user
