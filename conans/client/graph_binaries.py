from conans.util.files import rmdir, is_dirty
from conans.model.ref import PackageReference
from conans.client.output import ScopedOutput
from conans.errors import NotFoundException, NoRemoteAvailable
from conans.model.manifest import FileTreeManifest
import os


class GraphBinariesAnalyzer(object):
    def __init__(self, client_cache, output, remote_proxy):
        self._client_cache = client_cache
        self._out = output
        self._remote_proxy = remote_proxy

    def evaluate_graph(self, deps_graph, build_mode, update=False):
        """ given a DepsGraph object, build necessary nodes or retrieve them
        """
        # order by levels and separate the root node (conan_ref=None) from the rest
        for node in deps_graph.nodes:
            conan_ref, conanfile = node.conan_ref, node.conanfile
            if not conan_ref:
                continue
            if build_mode.forced(conanfile, conan_ref):
                node.binary = "BUILD"
                continue

            package_id = conanfile.info.package_id()
            package_ref = PackageReference(conan_ref, package_id)
            package_folder = self._client_cache.package(package_ref,
                                                        short_paths=conanfile.short_paths)

            with self._client_cache.package_lock(package_ref):
                if is_dirty(package_folder):
                    output = ScopedOutput(str(conan_ref), self._out)
                    output.warn("Package is corrupted, removing folder: %s" % package_folder)
                    rmdir(package_folder)

            if os.path.exists(package_folder):
                if update and self._check_update(package_folder, package_ref):
                    node.binary = "UPDATE"
                else:
                    node.binary = "INSTALLED"
            else:
                # check if remote exists
                if get_package_info(package_ref):
                    node.binary = "DOWNLOAD"  # SET REMOTE?
                else:
                    node.binary = "MISSING"
                    
            if build_mode.outdated:
                pass

    def _check_update(self, package_folder, package_ref):
        try:  # get_conan_digest can fail, not in server
            # FIXME: This can iterate remotes to get and associate in registry
            upstream_manifest = self._remote_proxy.get_package_manifest(package_ref)
        except NotFoundException:
            self._out.warn("Can't update, no package in remote")
        except NoRemoteAvailable:
            self._out.warn("Can't update, no remote defined")
        else:
            read_manifest = FileTreeManifest.load(package_folder)
            if upstream_manifest != read_manifest:
                if upstream_manifest.time > read_manifest.time:
                    self._out.warn("Current package is older than remote upstream one")
                    return True
                else:
                    self._out.warn("Current package is newer than remote upstream one")

    def _compute_private_nodes(self, deps_graph, build_mode):
        """ computes a list of nodes that are not required to be built, as they are
        private requirements of already available shared libraries as binaries.

        If the package requiring a private node has an up to date binary package,
        the private node is not retrieved nor built
        """
        skip_nodes = set()  # Nodes that require private packages but are already built
        for node in deps_graph.nodes:
            conan_ref, conanfile = node.conan_ref, node.conanfile
            if not [r for r in conanfile.requires.values() if r.private]:
                continue

            build_forced = build_mode.forced(conanfile, conan_ref)
            if build_forced:
                continue

            package_id = conanfile.info.package_id()
            package_reference = PackageReference(conan_ref, package_id)
            check_outdated = build_mode.outdated

            package_folder = self._client_cache.package(package_reference,
                                                        short_paths=conanfile.short_paths)
            if self._remote_proxy.package_available(package_reference,
                                                    package_folder,
                                                    check_outdated):
                skip_nodes.add(node)

        # Get the private nodes
        skippable_private_nodes = deps_graph.private_nodes(skip_nodes)
        return skippable_private_nodes

    def nodes_to_build(self, deps_graph):
        """Called from info command when a build policy is used in build_order parameter"""
        # Get the nodes in order and if we have to build them
        nodes_by_level = deps_graph.by_levels()
        nodes_by_level.pop()  # Remove latest one, consumer node with conan_ref=None
        skip_private_nodes = self._compute_private_nodes(deps_graph)
        nodes = self._get_nodes(nodes_by_level, skip_private_nodes)
        return [(PackageReference(node.conan_ref, package_id), node.conanfile)
                for node, package_id, build in nodes if build]

    def _get_nodes(self, nodes_by_level):
        """Compute a list of (conan_ref, package_id, conan_file, build_node)
        defining what to do with each node
        """

        nodes_to_build = []
        # Now build each level, starting from the most independent one
        package_references = set()
        for level in nodes_by_level:
            for node in level:
                if node in skip_nodes:
                    continue
                conan_ref, conan_file = node.conan_ref, node.conanfile
                build_node = False
                package_id = conan_file.info.package_id()
                package_reference = PackageReference(conan_ref, package_id)
                # Avoid processing twice the same package reference
                if package_reference not in package_references:
                    package_references.add(package_reference)
                    package_folder = self._client_cache.package(package_reference,
                                                                short_paths=conan_file.short_paths)

                    with self._client_cache.package_lock(package_reference):
                        if is_dirty(package_folder):
                            output = ScopedOutput(str(conan_ref), self._out)
                            output.warn("Package is corrupted, removing folder: %s" % package_folder)
                            rmdir(package_folder)
                    check_outdated = self._build_mode.outdated
                    if self._build_mode.forced(conan_file, conan_ref):
                        build_node = True
                    else:
                        available = self._remote_proxy.package_available(package_reference, package_folder,
                                                                         check_outdated)
                        build_node = not available

                nodes_to_build.append((node, package_id, build_node))

        # A check to be sure that if introduced a pattern, something is going to be built
        if self._build_mode.patterns:
            to_build = [str(n[0].conan_ref.name) for n in nodes_to_build if n[2]]
            self._build_mode.check_matches(to_build)

        return nodes_to_build
