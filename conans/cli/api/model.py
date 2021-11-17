class Remote:

    def __init__(self, name, url, verify_ssl=True, disabled=False, generic=False, username=None,
                 password=None):
        self._name = name  # Read only, is the key
        self.url = url
        self.verify_ssl = verify_ssl
        self.disabled = disabled
        self.generic = generic
        self.username = username
        self.password = password

    @property
    def name(self):
        return self._name

    def __eq__(self, other):
        if other is None:
            return False
        return self.name == other.name and \
               self.url == other.url and \
               self.verify_ssl == other.verify_ssl and \
               self.disabled == other.disabled and \
               self.generic == other.generic

    def __str__(self):
        ret = ""
        the_type = "generic" if self.generic else "conan"
        ret += "{}: {} [Verify SSL: {}, Enabled: {}, Type: {}]".format(self.name, self.url,
                                                                       self.verify_ssl,
                                                                       not self.disabled,
                                                                       the_type)
        return ret


class PackageConfiguration:

    def __init__(self, data):
        self.settings = data.get("settings", {})
        self.options = data.get("options", {})
        self.requires = data.get("requires", [])
