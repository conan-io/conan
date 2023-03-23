import fnmatch

from conans.errors import ConanException
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


class PackagesList:
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

    def add_prefs(self, rrev, prefs):
        # Prevs already come in ASCENDING order, so upload does older revisions first
        revs_dict = self.recipes[str(rrev)]["revisions"]
        rev_dict = revs_dict[rrev.revision]
        packages_dict = rev_dict.setdefault("packages", {})

        for pref in prefs:
            package_dict = packages_dict.setdefault(pref.package_id, {})
            if pref.revision:
                prevs_dict = package_dict.setdefault("revisions", {})
                prev_dict = prevs_dict.setdefault(pref.revision, {})
                if pref.timestamp:
                    prev_dict["timestamp"] = pref.timestamp

    def add_configurations(self, confs):
        for pref, conf in confs.items():
            rev_dict = self.recipes[str(pref.ref)]["revisions"][pref.ref.revision]
            try:
                rev_dict["packages"][pref.package_id]["info"] = conf
            except KeyError:  # If package_id does not exist, do nothing, only add to existing prefs
                pass

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


class ListPattern:

    def __init__(self, expression, rrev="latest", package_id=None, prev="latest", only_recipe=False):
        def split(s, c, default=None):
            if not s:
                return None, default
            tokens = s.split(c, 1)
            if len(tokens) == 2:
                return tokens[0], tokens[1] or default
            return tokens[0], default

        recipe, package = split(expression, ":")
        self.raw = expression
        self.ref, rrev = split(recipe, "#", rrev)
        ref, user_channel = split(self.ref, "@")
        self.name, self.version = split(ref, "/")
        self.user, self.channel = split(user_channel, "/")
        self.rrev, _ = split(rrev, "%")
        self.package_id, prev = split(package, "#", prev)
        self.prev, _ = split(prev, "%")
        if only_recipe:
            if self.package_id:
                raise ConanException("Do not specify 'package_id' with 'only-recipe'")
        else:
            self.package_id = self.package_id or package_id

    @property
    def is_latest_rrev(self):
        return self.rrev == "latest"

    @property
    def is_latest_prev(self):
        return self.prev == "latest"

    def check_refs(self, refs):
        if not refs and self.ref and "*" not in self.ref:
            raise ConanException(f"Recipe '{self.ref}' not found")

    def filter_rrevs(self, rrevs):
        if self.rrev == "!latest":
            return rrevs[1:]
        rrevs = [r for r in rrevs if fnmatch.fnmatch(r.revision, self.rrev)]
        if not rrevs:
            refs_str = f'{self.ref}#{self.rrev}'
            if "*" not in refs_str:
                raise ConanException(f"Recipe revision '{refs_str}' not found")
        return rrevs

    def filter_prefs(self, prefs):
        prefs = [p for p in prefs if fnmatch.fnmatch(p.package_id, self.package_id)]
        if not prefs:
            refs_str = f'{self.ref}#{self.rrev}:{self.package_id}'
            if "*" not in refs_str:
                raise ConanException(f"Package ID '{self.raw}' not found")
        return prefs

    def filter_prevs(self, prevs):
        if self.prev == "!latest":
            return prevs[1:]
        prevs = [p for p in prevs if fnmatch.fnmatch(p.revision, self.prev)]
        if not prevs:
            refs_str = f'{self.ref}#{self.rrev}:{self.package_id}#{self.prev}'
            if "*" not in refs_str:
                raise ConanException(f"Package revision '{self.raw}' not found")
        return prevs
