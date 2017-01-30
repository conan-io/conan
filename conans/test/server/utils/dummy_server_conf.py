"""
Generate a test server config 
"""
import random
import string
from passlib.apache import HtpasswdFile

test_server_conf = """[server]
jwt_secret: {jwt_secret}
jwt_expire_minutes: 120

ssl_enabled: False
port: 9300
public_port:
host_name: localhost

store_adapter: disk
authorize_timeout: 1800

disk_storage_path: {storage_path}
disk_authorize_timeout: 1800
updown_secret: {updown_secret}


[write_permissions]
{write_permissions}
[read_permissions]
{read_permissions}
[authentication]
{authentication}
[users]
{users}
"""

def _tuple_to_conf(t):
    # Converts a tuple to a config string
    return "%s: %s" % (t[0],t[1])

def create_dummy_server_conf(storage_path, read_permissions = ("*/*@*/*", "*"), write_permissions = (), users={"demo":"demo"}, authentication={"basic": ""}):
    """ Creates a dummy server conf
    storage_path: the path to the data
    read_permissions: default access to read
    write_permissions: default access to write (empty)
    users: dict of users 
    authentication: dict of authentication plugins
    """
    jwt_random_secret = ''.join(random.choice(string.ascii_letters) for _ in range(24))
    updown_random_secret = ''.join(random.choice(string.ascii_letters) for _ in range(24))
    server_conf = test_server_conf.format(jwt_secret=jwt_random_secret,
            updown_secret=updown_random_secret,
            storage_path=storage_path,
            users="\n".join(key + ": " + users[key] for key in users),
            read_permissions="\n".join(_tuple_to_conf(a) for a in read_permissions),
            write_permissions="\n".join(_tuple_to_conf(a) for a in write_permissions),
            authentication="\n".join(key + ": " + authentication[key] for key in authentication))
    return server_conf
 
def create_dummy_htpasswd(loc, users):
    ht = HtpasswdFile()
    for k in users:
        ht.set_password(k, users[k])
    ht.save(loc)