from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class Remote:

    def __init__(self, name, url, verify_ssl=True, disabled=False):
        self._name = name  # Read only, is the key
        self.url = url
        self.verify_ssl = verify_ssl
        self.disabled = disabled

    @property
    def name(self):
        return self._name

    def __eq__(self, other):
        if other is None:
            return False
        return self.name == other.name and \
               self.url == other.url and \
               self.verify_ssl == other.verify_ssl and \
               self.disabled == other.disabled

    def __str__(self):
        return "{}: {} [Verify SSL: {}, Enabled: {}]".format(self.name, self.url, self.verify_ssl,
                                                             not self.disabled)

    def __repr__(self):
        return str(self)


class SelectBundle:
    def __init__(self):
        self.recipes = {}

    def add_refs(self, refs):
        # RREVS alreday come in ASCENDING order, so upload does older revisions first
        for ref in refs:
            ref_dict = self.recipes.setdefault(str(ref), {})
            if ref.revision:
                revs_dict = ref_dict.setdefault("revisions", {})
                rev_dict = revs_dict.setdefault(ref.revision, {})
                if ref.timestamp:
                    rev_dict["timestamp"] = ref.timestamp

    def add_prefs(self, prefs):
        # Prevs already come in ASCENDING order, so upload does older revisions first
        for pref in prefs:
            revs_dict = self.recipes[str(pref.ref)]["revisions"]
            rev_dict = revs_dict[pref.ref.revision]
            packages_dict = rev_dict.setdefault("packages", {})
            package_dict = packages_dict.setdefault(pref.package_id, {})
            if pref.revision:
                prevs_dict = package_dict.setdefault("revisions", {})
                prev_dict = prevs_dict.setdefault(pref.revision, {})
                if pref.timestamp:
                    prev_dict["timestamp"] = pref.timestamp

    def add_configurations(self, confs):
        # Listed confs must already exist in bundle
        for pref, conf in confs.items():
            rev_dict = self.recipes[str(pref.ref)]["revisions"][pref.ref.revision]
            rev_dict["packages"][pref.package_id]["info"] = conf

    def refs(self):
        result = {}
        for ref, ref_dict in self.recipes.items():
            for rrev, rrev_dict in ref_dict.get("revisions", {}).items():
                t = rrev_dict.get("timestamp")
                recipe = RecipeReference.loads(f"{ref}#{rrev}%{t}")  # TODO: optimize this
                result[recipe] = rrev_dict
        return result.items()

    @staticmethod
    def prefs(ref, recipe_bundle):
        result = {}
        for package_id, pkg_bundle in recipe_bundle.get("packages", {}).items():
            prevs = pkg_bundle.get("revisions", {})
            for prev, prev_bundle in prevs.items():
                t = prev_bundle.get("timestamp")
                pref = PkgReference(ref, package_id, prev, t)
                result[pref] = prev_bundle
        return result.items()

    def serialize(self):
        return self.recipes
