from conans.client.graph.graph import BINARY_SKIP, \
    Overrides, BINARY_BUILD
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class InstallConfiguration:
    """ Represents a single, unique PackageReference to be downloaded, built, etc.
    Same PREF should only be built or downloaded once, but it is possible to have multiple
    nodes in the DepsGraph that share the same PREF.
    PREF could have PREV if to be downloaded (must be the same for all), but won't if to be built
    """
    def __init__(self):
        self.ref = None
        self.package_id = None
        self.prev = None
        self.nodes = []  # GraphNode
        self.binary = None  # The action BINARY_DOWNLOAD, etc must be the same for all nodes
        self.context = None  # Same PREF could be in both contexts, but only 1 context is enough to
        # be able to reproduce, typically host preferrably
        self.options = []  # to be able to fire a build, the options will be necessary
        self.filenames = []  # The build_order.json filenames e.g. "windows_build_order"
        self.depends = []  # List of full prefs
        self.overrides = Overrides()

    @property
    def pref(self):
        return PkgReference(self.ref, self.package_id, self.prev)

    @property
    def conanfile(self):
        return self.nodes[0].conanfile

    @staticmethod
    def create(node):
        result = InstallConfiguration()
        result.ref = node.ref
        result.package_id = node.pref.package_id
        result.prev = node.pref.revision
        result.binary = node.binary
        result.context = node.context
        # self_options are the minimum to reproduce state
        result.options = node.conanfile.self_options.dumps().splitlines()
        result.overrides = node.overrides()

        result.nodes.append(node)
        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                if dep.dst.pref not in result.depends:
                    result.depends.append(dep.dst.pref)
        return result

    def add(self, node):
        assert self.package_id == node.package_id, f"{self.pref}!={node.pref}"
        assert self.binary == node.binary, f"Binary for {node}: {self.binary}!={node.binary}"
        assert self.prev == node.prev
        # The context might vary, but if same package_id, all fine
        # assert self.context == node.context
        self.nodes.append(node)

        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                if dep.dst.pref not in self.depends:
                    self.depends.append(dep.dst.pref)

    def _build_args(self):
        if self.binary != BINARY_BUILD:
            return None
        cmd = f"--require={self.ref}" if self.context == "host" else f"--tool-require={self.ref}"
        cmd += f" --build={self.ref}"
        if self.options:
            cmd += " " + " ".join(f"-o {o}" for o in self.options)
        if self.overrides:
            cmd += f' --lockfile-overrides="{self.overrides}"'
        return cmd

    def serialize(self):
        return {"ref": self.ref.repr_notime(),
                "pref": self.pref.repr_notime(),
                "package_id": self.pref.package_id,
                "prev": self.pref.revision,
                "context": self.context,
                "binary": self.binary,
                "options": self.options,
                "filenames": self.filenames,
                "depends": [d.repr_notime() for d in self.depends],
                "overrides": self.overrides.serialize(),
                "build_args": self._build_args()
                }

    @staticmethod
    def deserialize(data, filename):
        result = InstallConfiguration()
        result.ref = RecipeReference.loads(data["ref"])
        result.package_id = data["package_id"]
        result.prev = data["prev"]
        result.binary = data["binary"]
        result.context = data["context"]
        result.options = data["options"]
        result.filenames = data["filenames"] or [filename]
        result.depends = [PkgReference.loads(p) for p in data["depends"]]
        result.overrides = Overrides.deserialize(data["overrides"])
        return result

    def merge(self, other):
        assert self.ref == other.ref
        for d in other.depends:
            if d not in self.depends:
                self.depends.append(d)

        for d in other.filenames:
            if d not in self.filenames:
                self.filenames.append(d)
