import time

from conans.model.conan_file import get_env_context_manager
from conans.model.requires import Requirements
from conans.model.ref import ConanFileReference
from conans.errors import (ConanException, conanfile_exception_formatter,
                           ConanExceptionInUserConanfileMethod)
from conans.client.output import ScopedOutput
from conans.util.log import logger
from conans.client.graph.graph import DepsGraph, Node, RECIPE_WORKSPACE
from conans.model.workspace import WORKSPACE_FILE


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

    def load_graph(self, conanfile, check_updates, update, remote_name, processed_profile):
        check_updates = check_updates or update
        dep_graph = DepsGraph()
        # compute the conanfile entry point for this dependency graph
        root_node = Node(None, conanfile)
        dep_graph.add_node(root_node)
        public_deps = {}  # {name: Node} dict with public nodes, so they are not added again
        aliased = {}
        # enter recursive computation
        t1 = time.time()
        loop_ancestors = []
        self._load_deps(root_node, Requirements(), dep_graph, public_deps, None, None,
                        loop_ancestors, aliased, check_updates, update, remote_name,
                        processed_profile)
        logger.debug("Deps-builder: Time to load deps %s" % (time.time() - t1))
        t1 = time.time()
        dep_graph.compute_package_ids()
        logger.debug("Deps-builder: Propagate info %s" % (time.time() - t1))
        return dep_graph

    def _resolve_deps(self, node, aliased, update, remote_name):
        # Resolve possible version ranges of the current node requirements
        # new_reqs is a shallow copy of what is propagated upstream, so changes done by the
        # RangeResolver are also done in new_reqs, and then propagated!
        conanfile, conanref = node.conanfile, node.conan_ref
        for _, require in conanfile.requires.items():
            self._resolver.resolve(require, conanref, update, remote_name)

        # After resolving ranges,
        for req in conanfile.requires.values():
            alias = aliased.get(req.conan_reference)
            if alias:
                req.conan_reference = alias

        if not hasattr(conanfile, "_conan_evaluated_requires"):
            conanfile._conan_evaluated_requires = conanfile.requires.copy()
        elif conanfile.requires != conanfile._conan_evaluated_requires:
            raise ConanException("%s: Incompatible requirements obtained in different "
                                 "evaluations of 'requirements'\n"
                                 "    Previous requirements: %s\n"
                                 "    New requirements: %s"
                                 % (conanref, list(conanfile._conan_evaluated_requires.values()),
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
            if require.conan_reference in loop_ancestors:
                raise ConanException("Loop detected: %s"
                                     % "->".join(str(r) for r in loop_ancestors))
            new_loop_ancestors = loop_ancestors[:]  # Copy for propagating
            new_loop_ancestors.append(require.conan_reference)
            previous = public_deps.get(name)
            if require.private or not previous:  # new node, must be added and expanded
                new_node = self._create_new_node(node, dep_graph, require, public_deps, name,
                                                 aliased, check_updates, update, remote_name,
                                                 processed_profile)
                # RECURSION!
                # Make sure the subgraph is truly private
                new_public_deps = {} if require.private else public_deps
                self._load_deps(new_node, new_reqs, dep_graph, new_public_deps, node.conan_ref,
                                new_options, new_loop_ancestors, aliased, check_updates, update,
                                remote_name, processed_profile)
            else:  # a public node already exist with this name
                previous_node, closure = previous
                alias_ref = aliased.get(require.conan_reference, require.conan_reference)
                # Necessary to make sure that it is pointing to the correct aliased
                require.conan_reference = alias_ref
                if previous_node.conan_ref != alias_ref:
                    raise ConanException("Conflict in %s\n"
                                         "    Requirement %s conflicts with already defined %s\n"
                                         "    Keeping %s\n"
                                         "    To change it, override it in your base requirements"
                                         % (node.conan_ref, require.conan_reference,
                                            previous_node.conan_ref, previous_node.conan_ref))
                dep_graph.add_edge(node, previous_node)
                # RECURSION!
                if closure is None:
                    closure = dep_graph.closure(node)
                    public_deps[name] = previous_node, closure
                if self._recurse(closure, new_reqs, new_options):
                    self._load_deps(previous_node, new_reqs, dep_graph, public_deps, node.conan_ref,
                                    new_options, new_loop_ancestors, aliased, check_updates, update,
                                    remote_name, processed_profile)

    def _recurse(self, closure, new_reqs, new_options):
        """ For a given closure, if some requirements or options coming from downstream
        is incompatible with the current closure, then it is necessary to recurse
        then, incompatibilities will be raised as usually"""
        for req in new_reqs.values():
            n = closure.get(req.conan_reference.name)
            if n and n.conan_ref != req.conan_reference:
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
            conanfile, conanref = node.conanfile, node.conan_ref
            # Avoid extra time manipulating the sys.path for python
            with get_env_context_manager(conanfile, without_python=True):
                if hasattr(conanfile, "config"):
                    if not conanref:
                        output = ScopedOutput(str("PROJECT"), self._output)
                        output.warn("config() has been deprecated."
                                    " Use config_options and configure")
                    with conanfile_exception_formatter(str(conanfile), "config"):
                        conanfile.config()
                with conanfile_exception_formatter(str(conanfile), "config_options"):
                    conanfile.config_options()
                conanfile.options.propagate_upstream(down_options, down_ref, conanref)
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
                        req.conan_reference = aliased.get(req.conan_reference,
                                                          req.conan_reference)
                new_down_reqs = conanfile.requires.update(down_reqs, self._output,
                                                          conanref, down_ref)
        except ConanExceptionInUserConanfileMethod:
            raise
        except ConanException as e:
            raise ConanException("%s: %s" % (conanref or "Conanfile", str(e)))
        except Exception as e:
            raise ConanException(e)

        return new_down_reqs, new_options

    def _create_new_node(self, current_node, dep_graph, requirement, public_deps, name_req, aliased,
                         check_updates, update, remote_name, processed_profile, alias_ref=None):
        """ creates and adds a new node to the dependency graph
        """
        workspace_package = self._workspace[requirement.conan_reference] if self._workspace else None
        if workspace_package:
            conanfile_path = workspace_package.conanfile_path
            recipe_status = RECIPE_WORKSPACE
            remote = WORKSPACE_FILE
        else:
            try:
                result = self._proxy.get_recipe(requirement.conan_reference,
                                                check_updates, update, remote_name, self._recorder)
            except ConanException as e:
                base_ref = str(current_node.conan_ref or "PROJECT")
                self._output.error("Failed requirement '%s' from '%s'"
                                   % (requirement.conan_reference, base_ref))
                raise e
            conanfile_path, recipe_status, remote, _ = result

        output = ScopedOutput(str(requirement.conan_reference), self._output)
        dep_conanfile = self._loader.load_conanfile(conanfile_path, output, processed_profile,
                                                    reference=requirement.conan_reference)

        if workspace_package:
            workspace_package.conanfile = dep_conanfile
        if getattr(dep_conanfile, "alias", None):
            alias_reference = alias_ref or requirement.conan_reference
            requirement.conan_reference = ConanFileReference.loads(dep_conanfile.alias)
            aliased[alias_reference] = requirement.conan_reference
            return self._create_new_node(current_node, dep_graph, requirement, public_deps,
                                         name_req, aliased, check_updates, update,
                                         remote_name, processed_profile, alias_ref=alias_reference)

        new_node = Node(requirement.conan_reference, dep_conanfile)
        new_node.recipe = recipe_status
        new_node.remote = remote
        dep_graph.add_node(new_node)
        dep_graph.add_edge(current_node, new_node, requirement.private)
        if not requirement.private:
            public_deps[name_req] = new_node, None
        return new_node
