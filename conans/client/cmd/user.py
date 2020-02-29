from conans.client.store.localdb import LocalDB
from conans.errors import ConanException


def users_list(localdb_file, remotes):
    if not remotes:
        raise ConanException("No remotes defined")

    localdb = LocalDB.create(localdb_file)
    remotes_info = []
    for remote in remotes:
        user_info = {}
        user, token, _ = localdb.get_login(remote.url)
        user_info["name"] = remote.name
        user_info["user_name"] = user
        user_info["authenticated"] = True if token else False
        remotes_info.append(user_info)
    return remotes_info


def token_present(localdb_file, remote, user):
    localdb = LocalDB.create(localdb_file)
    current_user, token, _ = localdb.get_login(remote.url)
    return token is not None and (user is None or user == current_user)


def users_clean(localdb_file):
    LocalDB.create(localdb_file, clean=True)


def user_set(localdb_file, user, remote_name=None):
    localdb = LocalDB.create(localdb_file)

    if user.lower() == "none":
        user = None
    return update_localdb(localdb, user, token=None, refresh_token=None, remote=remote_name)


def update_localdb(localdb, user, token, refresh_token, remote):
    previous_user = localdb.get_username(remote.url)
    localdb.store(user, token, refresh_token, remote.url)
    return remote.name, previous_user, user
