from conans.model.ref import ConanName


class Username(str):

    def __new__(cls, name):
        """Simple name creation.

        @param name:        string containing the desired name
        """
        ConanName.validate_user(name)
        return str.__new__(cls, name)
