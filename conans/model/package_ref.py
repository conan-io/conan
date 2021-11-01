from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


class PkgReference:

    def __init__(self, ref=None, package_id=None, revision=None, timestamp=None):
        self.ref = ref
        self.package_id = package_id
        self.revision = revision
        self.timestamp = timestamp  # TODO: Which format? int timestamp?

    @property
    def id(self):
        # This is temporary helper to migrate without tons of changes, can be removed later
        return self.package_id

    @staticmethod
    def from_conanref(pref, timestamp=None):
        return PkgReference(pref.ref, pref.id, pref.revision, timestamp)

    def __repr__(self):
        """ long repr like pkg/0.1@user/channel#rrev%timestamp """
        if self.ref is None:
            return ""
        result = repr(self.ref)
        if self.package_id:
            result += ":{}".format(self.package_id)
        if self.revision is not None:
            result += "#{}".format(self.revision)
        if self.timestamp is not None:
            result += "%{}".format(self.timestamp)
        return result

    def __str__(self):
        """ shorter representation, excluding the revision and timestamp """
        if self.ref is None:
            return ""
        result = str(self.ref)
        if self.package_id:
            result += ":{}".format(self.package_id)
        return result

    def __lt__(self, ref):
        # The timestamp goes before the revision for ordering revisions chronologically
        raise Exception("WHO IS COMPARING PACKAGE REFERENCES?")
        # return (self.name, self.version, self.user, self.channel, self.timestamp, self.revision) \
        #       < (ref.name, ref.version, ref.user, ref.channel, ref.timestamp, ref.revision)

    def __eq__(self, other):
        # TODO: In case of equality, should it use the revision and timestamp?
        raise Exception("WHO IS COMPARING PACKAGE REFERENCES?")
        # return self.__dict__ == other.__dict__

    def __hash__(self):
        raise Exception("WHO IS COMPARING RECIPE REFERENCES?")
        # return hash((self.name, self.version, self.user, self.channel, self.revision))

    @staticmethod
    def loads(text):  # TODO: change this default to validate only on end points
        try:
            tokens = text.split(":", 1)
            assert len(tokens) == 2
            ref, pkg_id = tokens

            ref = RecipeReference.loads(ref)

            # timestamp
            tokens = pkg_id.rsplit("%", 1)
            text = tokens[0]
            timestamp = int(tokens[1]) if len(tokens) == 2 else None

            # revision
            tokens = text.split("#", 1)
            package_id = tokens[0]
            revision = tokens[1] if len(tokens) == 2 else None

            return PkgReference(ref, package_id, revision, timestamp)
        except Exception:
            raise ConanException(
                f"{text} is not a valid package reference, provide a reference"
                f" in the form name/version[@user/channel:package_id]")
