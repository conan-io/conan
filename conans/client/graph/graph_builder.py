import time

from conans.client.graph.graph import DepsGraph, Node, RECIPE_WORKSPACE,\
    RECIPE_EDITABLE
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.conan_file import get_env_context_manager
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirements
from conans.model.workspace import WORKSPACE_FILE
from conans.util.log import logger

REFERENCE_CONFLICT, REVISION_CONFLICT = 1, 2


class DepsGraphBuilder(object):
    """ Responsible for computing the dependencies graph DepsGraph
    """
    def __init__(self, proxy, output, loader, resolver, workspace, recorder):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._resolver = resolver
        self._workspace = workspace
        self._recorder = recorder

    def load_graph(self, root_node, check_updates, update, remote_name, processed_profile):
        check_updates = check_updates or update
        dep_graph = DepsGraph()
        # compute the conanfile entry point for this dependency graph
        dep_graph.add_node(root_node)
        public_deps = {}  # {name: Node} dict with public nodes, so they are not added again
        aliased = {}
        # enter recursive computation
        t1 = time.time()
        loop_ancestors = []
        self._load_deps(root_node, Requirements(), dep_graph, public_deps, None, None,
                        loop_ancestors, aliased, check_updates, update, remote_name,
                        processed_profile)
        logger.debug("GRAPH: Time to load deps %s" % (time.time() - t1))
        t1 = time.time()
        dep_graph.compute_package_ids()
        logger.debug("GRAPH: Propagate info %s" % (time.time() - t1))
        return dep_graph

    def _resolve_deps(self, node, aliased, update, remote_name):
        # Resolve possible version ranges of the current node requirements
        # new_reqs is a shallow copy of what is propagated upstream, so changes done by the
        # RangeResolver are also done in new_reqs, and then propagated!
        conanfile = node.conanfile
        scope = conanfile.display_name
        for _, require in conanfile.requires.items():
            self._resolver.resolve(require, scope, update, remote_name)

        # After resolving ranges,
        for require in conanfile.requires.values():
            alias = aliased.get(require.ref)
            if alias:
                require.ref = alias

        if not hasattr(conanfile, "_conan_evaluated_requires"):
            conanfile._conan_evaluated_requires = conanfile.requires.copy()
        elif conanfile.requires != conanfile._conan_evaluated_requires:
            raise ConanException("%s: Incompatible requirements obtained in different "
                                 "evaluations of 'requirements'\n"
                                 "    Previous requirements: %s\n"
                                 "    New requirements: %s"
                                 % (scope, list(conanfile._conan_evaluated_requires.values()),
                                    list(conanfile.requires.values())))

    def _load_deps(self, node, down_reqs, dep_graph, public_deps, down_ref, down_options,
                   loop_ancestors, aliased, check_updates, update, remote_name, processed_profile):
        """ loads a Conan object from the given file
        param node: Node object to be expanded in this step
        down_reqs: the Requirements as coming from downstream, which can overwrite current
                    values
        param deps: DepsGraph result
        param public_deps: {name: Node} of already expanded public Nodes, not to be repeated
                           in graph
        param down_ref: ConanFileReference of who is depending on current node for this expansion
        """
        # basic node configuration
        new_reqs, new_options = self._config_node(node, down_reqs, down_ref, down_options, aliased)

        self._resolve_deps(node, aliased, update, remote_name)

        # Expand each one of the current requirements
        for name, require in node.conanfile.requires.items():
            if require.override:
                continue
            if require.ref in loop_ancestors:
                raise ConanException("Loop detected: %s"
                                     % "->".join(str(r) for r in loop_ancestors))
            new_loop_ancestors = loop_ancestors[:]  # Copy for propagating
            new_loop_ancestors.append(require.ref)
            previous = public_deps.get(name)
            if require.private or not previous:  # new node, must be added and expanded
                new_node = self._create_new_node(node, dep_graph, require, public_deps, name,
                                                 aliased, check_updates, update, remote_name,
                                                 processed_profile)
                # RECURSION!
                # Make sure the subgraph is truly private
                new_public_deps = {} if require.private else public_deps
                self._load_deps(new_node, new_reqs, dep_graph, new_public_deps, node.ref,
                                new_options, new_loop_ancestors, aliased, check_updates, update,
                                remote_name, processed_profile)
            else:  # a public node already exist with this name
                previous_node, closure = previous
                alias_ref = aliased.get(require.ref, None)
                # Necessary to make sure that it is pointing to the correct aliased
                if alias_ref:
                    require.ref = alias_ref
                conflict = self._conflicting_references(previous_node.ref, require.ref)
                if conflict == REVISION_CONFLICT:  # Revisions conflict
                    raise ConanException("Conflict in %s\n"
                                         "    Different revisions of %s has been requested"
                                         % (node.ref, require.ref))
                elif conflict == REFERENCE_CONFLICT:
                    raise ConanException("Conflict in %s\n"
                                         "    Requirement %s conflicts with already defined %s\n"
                                         "    Keeping %s\n"
                                         "    To change it, override it in your base requirements"
                                         % (node.ref, require.ref,
                                            previous_node.ref, previous_node.ref))

                dep_graph.add_edge(node, previous_node)
                # RECURSION!
                if closure is None:
                    closure = dep_graph.closure(node)
                    public_deps[name] = previous_node, closure
                if self._recurse(closure, new_reqs, new_options):
                    self._load_deps(previous_node, new_reqs, dep_graph, public_deps, node.ref,
                                    new_options, new_loop_ancestors, aliased, check_updates, update,
                                    remote_name, processed_profile)

    @staticmethod
    def _conflicting_references(previous_ref, new_ref):
        if previous_ref.copy_clear_rev() != new_ref.copy_clear_rev():
            return REFERENCE_CONFLICT
        # Computed node, if is Editable, has revision=None
        # If new_ref.revision is None we cannot assume any conflict, the user hasn't specified
        # a revision, so it's ok any previous_ref
        if previous_ref.revision and new_ref.revision and previous_ref.revision != new_ref.revision:
            return REVISION_CONFLICT
        return False

    def _recurse(self, closure, new_reqs, new_options):
        """ For a given closure, if some requirements or options coming from downstream
        is incompatible with the current closure, then it is necessary to recurse
        then, incompatibilities will be raised as usually"""
        for req in new_reqs.values():
            n = closure.get(req.ref.name)
            if n and self._conflicting_references(n.ref, req.ref):
                return True
        for pkg_name, options_values in new_options.items():
            n = closure.get(pkg_name)
            if n:
                options = n.conanfile.options
                for option, value in options_values.items():
                    if getattr(options, option) != value:
                        return True
        return False

    def _config_node(self, node, down_reqs, down_ref, down_options, aliased):
        """ update settings and option in the current ConanFile, computing actual
        requirement values, cause they can be overridden by downstream requires
        param settings: dict of settings values => {"os": "windows"}
        """
        try:
            conanfile, ref = node.conanfile, node.ref
            # Avoid extra time manipulating the sys.path for python
            with get_env_context_manager(conanfile, without_python=True):
                if hasattr(conanfile, "config"):
                    if not ref:
                        conanfile.output.warn("config() has been deprecated."
                                              " Use config_options and configure")
                    with conanfile_exception_formatter(str(conanfile), "config"):
                        conanfile.config()
                with conanfile_exception_formatter(str(conanfile), "config_options"):
                    conanfile.config_options()
                conanfile.options.propagate_upstream(down_options, down_ref, ref)
                if hasattr(conanfile, "config"):
                    with conanfile_exception_formatter(str(conanfile), "config"):
                        conanfile.config()

                with conanfile_exception_formatter(str(conanfile), "configure"):
                    conanfile.configure()

                conanfile.settings.validate()  # All has to be ok!
                conanfile.options.validate()

                # Update requirements (overwrites), computing new upstream
                if hasattr(conanfile, "requirements"):
                    # If re-evaluating the recipe, in a diamond graph, with different options,
                    # it could happen that one execution path of requirements() defines a package
                    # and another one a different package raising Duplicate dependency error
                    # Or the two consecutive calls, adding 2 different dependencies for the two paths
                    # So it is necessary to save the "requires" state and restore it before a second
                    # execution of requirements(). It is a shallow copy, if first iteration is
                    # RequireResolve'd or overridden, the inner requirements are modified
                    if not hasattr(conanfile, "_conan_original_requires"):
                        conanfile._conan_original_requires = conanfile.requires.copy()
                    else:
                        conanfile.requires = conanfile._conan_original_requires.copy()

                    with conanfile_exception_formatter(str(conanfile), "requirements"):
                        conanfile.requirements()

                new_options = conanfile.options.deps_package_values
                if aliased:
                    for req in conanfile.requires.values():
                        req.ref = aliased.get(req.ref, req.ref)
                new_down_reqs = conanfile.requires.update(down_reqs, self._output, ref, down_ref)
        except ConanExceptionInUserConanfileMethod:
            raise
        except ConanException as e:
            raise ConanException("%s: %s" % (ref or "Conanfile", str(e)))
        except Exception as e:
            raise ConanException(e)

        return new_down_reqs, new_options

    def _create_new_node(self, current_node, dep_graph, requirement, public_deps, name_req, aliased,
                         check_updates, update, remote_name, processed_profile, alias_ref=None):
        """ creates and adds a new node to the dependency graph
        """
        workspace_package = self._workspace[requirement.ref] if self._workspace else None

        if workspace_package:
            conanfile_path = workspace_package.conanfile_path
            recipe_status = RECIPE_WORKSPACE
            remote = WORKSPACE_FILE
            new_ref = requirement.ref
        else:
            try:
                result = self._proxy.get_recipe(requirement.ref,
                                                check_updates, update, remote_name, self._recorder)
            except ConanException as e:
                if current_node.ref:
                    self._output.error("Failed requirement '%s' from '%s'"
                                       % (requirement.ref,
                                          current_node.conanfile.display_name))
                raise e
            conanfile_path, recipe_status, remote, new_ref = result

        dep_conanfile = self._loader.load_conanfile(conanfile_path, processed_profile,
                                                    ref=requirement.ref)
        if recipe_status == RECIPE_EDITABLE:
            dep_conanfile.in_local_cache = False

        if workspace_package:
            workspace_package.conanfile = dep_conanfile
        if getattr(dep_conanfile, "alias", None):
            alias_ref = alias_ref or new_ref.copy_clear_rev()
            requirement.ref = ConanFileReference.loads(dep_conanfile.alias)
            aliased[alias_ref] = requirement.ref
            return self._create_new_node(current_node, dep_graph, requirement, public_deps,
                                         name_req, aliased, check_updates, update,
                                         remote_name, processed_profile,
                                         alias_ref=alias_ref)

        logger.debug("GRAPH: new_node: %s" % str(new_ref))
        new_node = Node(new_ref, dep_conanfile)
        new_node.revision_pinned = requirement.ref.revision is not None
        new_node.recipe = recipe_status
        new_node.remote = remote
        dep_graph.add_node(new_node)
        dep_graph.add_edge(current_node, new_node, requirement.private)
        if not requirement.private:
            public_deps[name_req] = new_node, None
        return new_node
