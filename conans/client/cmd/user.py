from conans.errors import ConanException
from conans.client.store.localdb import LocalDB


def users_list(client_cache, registry, remote_name, output):
    # List all users from required remotes
    remotes = [registry.remote(remote_name)] if remote_name else registry.remotes

    if not remotes:
        raise ConanException("No remotes defined")

    localdb = LocalDB(client_cache.localdb)
    result = []
    for remote in remotes:
        user, token = localdb.get_login(remote.url)
        authenticated = " [Authenticated]" if token else ""
        anonymous = " (anonymous)" if not user else ""
        output.info("Current '%s' remote's user: '%s'%s%s" %
                    (remote.name, str(user), anonymous, authenticated))
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
    previous_username = previous_user or "None"
    previous_anonymous = " (anonymous)" if not previous_user else ""
    username = user or "None"
    anonymous = " (anonymous)" if not user else ""

    if previous_user == user:
        output.info("'%s' remote's user is already '%s'%s" %
                    (remote.name, previous_username, previous_anonymous))
    else:
        output.info("Changed '%s' remote's user from '%s'%s to '%s'%s" %
                    (remote.name, previous_username, previous_anonymous, username, anonymous))
