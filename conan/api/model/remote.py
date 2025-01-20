LOCAL_RECIPES_INDEX = "local-recipes-index"


class Remote:

    def __init__(self, name, url, verify_ssl=True, disabled=False, allowed_packages=None,
                 remote_type=None):
        self.name = name  # Read only, is the key
        self.url = url
        self.verify_ssl = verify_ssl
        self.disabled = disabled
        self.allowed_packages = allowed_packages
        self.remote_type = remote_type
        self.caching = {}

    def __eq__(self, other):
        if other is None:
            return False
        return (self.name == other.name and self.url == other.url and
                self.verify_ssl == other.verify_ssl and self.disabled == other.disabled)

    def __str__(self):
        allowed_msg = ""
        if self.allowed_packages:
            allowed_msg = ", Allowed packages: {}".format(", ".join(self.allowed_packages))
        if self.remote_type == LOCAL_RECIPES_INDEX:
            return "{}: {} [{}, Enabled: {}{}]".format(self.name, self.url, LOCAL_RECIPES_INDEX,
                                                       not self.disabled, allowed_msg)
        return "{}: {} [Verify SSL: {}, Enabled: {}{}]".format(self.name, self.url, self.verify_ssl,
                                                               not self.disabled, allowed_msg)

    def __repr__(self):
        return str(self)

    def invalidate_cache(self):
        # TODO: make it private
        self.caching = {}
