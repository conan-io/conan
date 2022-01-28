from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.util.dates import timestamp_to_str


class PkgReference:

    def __init__(self, ref=None, package_id=None, revision=None, timestamp=None):
        self.ref = ref
        self.package_id = package_id
        self.revision = revision
        self.timestamp = timestamp  # float, Unix seconds UTC

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

    def repr_notime(self):
        if self.ref is None:
            return ""
        result = self.ref.repr_notime()
        if self.package_id:
            result += ":{}".format(self.package_id)
        if self.revision is not None:
            result += "#{}".format(self.revision)
        return result

    def repr_reduced(self):
        if self.ref is None:
            return ""
        result = self.ref.repr_reduced()
        if self.package_id:
            result += ":{}".format(self.package_id[0:4])
        if self.revision is not None:
            result += "#{}".format(self.revision[0:4])
        return result

    def repr_humantime(self):
        result = self.repr_notime()
        assert self.timestamp
        result += " ({})".format(timestamp_to_str(self.timestamp))
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
        #       < (ref.name, ref.version, ref.user, ref.channel, ref._timestamp, ref.revision)

    def __eq__(self, other):
        # TODO: In case of equality, should it use the revision and timestamp?
        # Used:
        #    at "graph_binaries" to check: cache_latest_prev != pref
        #    at "installer" to check: if pkg_layout.reference != pref (probably just optimization?)
        #    at "revisions_test"
        return self.ref == other.ref and self.revision == other.revision

    def __hash__(self):
        # Used in dicts of PkgReferences as keys like the cached nodes in the graph binaries
        return hash((self.ref, self.package_id, self.revision))

    @staticmethod
    def loads(pkg_ref):  # TODO: change this default to validate only on end points
        try:
            tokens = pkg_ref.split(":", 1)
            assert len(tokens) == 2
            ref, pkg_id = tokens

            ref = RecipeReference.loads(ref)

            # timestamp
            tokens = pkg_id.rsplit("%", 1)
            text = tokens[0]
            timestamp = float(tokens[1]) if len(tokens) == 2 else None

            # revision
            tokens = text.split("#", 1)
            package_id = tokens[0]
            revision = tokens[1] if len(tokens) == 2 else None

            return PkgReference(ref, package_id, revision, timestamp)
        except Exception:
            raise ConanException(
                f"{pkg_ref} is not a valid package reference, provide a reference"
                f" in the form name/version[@user/channel:package_id]")
