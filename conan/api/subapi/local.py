import os
from typing import List

from conan.cli import make_abs_path
from conan.internal.conan_app import ConanApp
from conan.internal.api.local.editable import EditablePackages
from conan.internal.methods import run_build_method, run_source_method
from conan.internal.graph.graph import CONTEXT_HOST
from conan.internal.graph.profile_node_definer import initialize_conanfile_profile
from conan.internal.errors import conanfile_exception_formatter
from conan.errors import ConanException
from conan.api.model import RecipeReference, Remote
from conan.internal.util.files import chdir


class LocalAPI:
    """ This ``LocalAPI`` contains several helpers related to the local development flow, i.e.,
    locally calling ``source()`` or ``build()`` methods, or adding and removing editable packages
    """

    def __init__(self, conan_api, helpers):
        self._conan_api = conan_api
        self._helpers = helpers
        self.editable_packages = EditablePackages(conan_api.home_folder)

    @staticmethod
    def get_conanfile_path(path, cwd, py):
        """ Obtain the full path to a conanfile file, either .txt or .py, from the current
        working directory.

        If both ``conanfile.py`` and a ``conanfile.txt`` are present, it will raise an error.

        :param path: Relative path to look for the file. Can be a folder or a file.
        :param cwd: The current working directory.
        :param py: If True, a conanfile.py must exist, a .txt is not valid in this case
        """
        path = make_abs_path(path, cwd)

        if os.path.isdir(path):  # Can be a folder
            path_py = os.path.join(path, "conanfile.py")
            if py:
                path = path_py
            else:
                path_txt = os.path.join(path, "conanfile.txt")
                if os.path.isfile(path_py) and os.path.isfile(path_txt):
                    raise ConanException("Ambiguous command, both conanfile.py and "
                                         "conanfile.txt exist")
                path = path_py if os.path.isfile(path_py) else path_txt

        if not os.path.isfile(path):  # Must exist
            raise ConanException("Conanfile not found at %s" % path)

        if py and not path.endswith(".py"):
            raise ConanException("A conanfile.py is needed, " + path + " is not acceptable")

        return path

    def editable_add(self, path, name=None, version=None, user=None, channel=None, cwd=None,
                     output_folder=None, remotes: List[Remote] = None) -> RecipeReference:
        """ Add the conanfile in the given path as an editable package

        Note that for automation over editables it might be recommended to use the ``WorkspacesAPI``
        instead of this API.

        :param path: Relative path to look for it. Can be a folder or a file.
        :param name: The name of the package. If not defined, it is taken from conanfile
        :param version: The version of the package. If not defined, it is taken from conanfile
        :param user: The user of the package. If not defined, it is taken from conanfile
        :param channel: The channel of the package. If not defined, it is taken from conanfile
        :param cwd: The current working directory
        :param output_folder: The output folder. If not defined, the recipe layout will be used.
        :param remotes: The remotes to resolve possible ``python-requires`` for this recipe if needed.
        :return: RecipeReference of the added package
        """
        path = self.get_conanfile_path(path, cwd, py=True)
        app = ConanApp(self._conan_api)
        conanfile = app.loader.load_named(path, name, version, user, channel, remotes=remotes)
        if conanfile.name is None or conanfile.version is None:
            raise ConanException("Editable package recipe should declare its name and version")
        ref = RecipeReference(conanfile.name, conanfile.version, conanfile.user, conanfile.channel)
        # Retrieve conanfile.py from target_path
        target_path = self.get_conanfile_path(path=path, cwd=cwd, py=True)
        output_folder = make_abs_path(output_folder) if output_folder else None
        # Check the conanfile is there, and name/version matches
        self.editable_packages.add(ref, target_path, output_folder=output_folder)
        return ref

    def editable_remove(self, path=None, requires=None, cwd=None):
        """ Remove an editable package from the given path

        Note that for automation over editables it might be recommended to use the ``WorkspacesAPI``
        instead of this API.

        :param path: Relative path to look for it. Can be a folder or a file.
        :param requires: Remove these requirements from editables (instead of by path)
        :param cwd: The current working directory
        :return: RecipeReference of the added package
        """
        if path:
            path = make_abs_path(path, cwd)
            path = os.path.join(path, "conanfile.py")
        return self.editable_packages.remove(path, requires)

    def editable_list(self):
        return self.editable_packages.edited_refs

    def source(self, path, name=None, version=None, user=None, channel=None,
               remotes: List[Remote] = None):
        """ Calls the ``source()`` method of the current (user folder) ``conanfile.py``

        This method does not require computing a dependency graph, because the ``source()``
        method is assumed to be invariant with respect to settings, options and dependencies.

        :param path: Relative path to look for the conanfile. Can be a folder or a file.
        :param name: The name of the package. If not defined, it is taken from conanfile
        :param version: The version of the package. If not defined, it is taken from conanfile
        :param user: The user of the package. If not defined, it is taken from conanfile
        :param channel: The channel of the package. If not defined, it is taken from conanfile
        :param remotes: The remotes to resolve possible ``python-requires`` for this recipe if needed.
        """
        app = ConanApp(self._conan_api)
        conanfile = app.loader.load_consumer(path, name=name, version=version,
                                             user=user, channel=channel, graph_lock=None,
                                             remotes=remotes)
        # This profile is empty, but with the conf from global.conf
        profile = self._conan_api.profiles.get_profile([])
        initialize_conanfile_profile(conanfile, profile, profile, CONTEXT_HOST, False)
        # This is important, otherwise the ``conan source`` doesn't define layout and fails
        if hasattr(conanfile, "layout"):
            with conanfile_exception_formatter(conanfile, "layout"):
                conanfile.layout()

        folder = conanfile.recipe_folder if conanfile.folders.root is None else \
            os.path.normpath(os.path.join(conanfile.recipe_folder, conanfile.folders.root))

        conanfile.folders.set_base_source(folder)
        conanfile.folders.set_base_export_sources(folder)
        conanfile.folders.set_base_recipe_metadata(os.path.join(folder, "metadata"))
        # The generators are needed for the "conan source" local case with tool-requires
        conanfile.folders.set_base_generators(folder)
        conanfile.folders.set_base_build(None)
        conanfile.folders.set_base_package(None)

        hook_manager = self._helpers.hook_manager
        run_source_method(conanfile, hook_manager)

    def build(self, conanfile) -> None:
        """ Calls the ``build()`` method of the current (user folder) ``conanfile.py``

        This method does require computing a dependency graph, because the ``build()`` method
        needs all dependencies and transitive dependencies. Then, the ``conanfile`` argument
        must be the one obtaind from a full dependency graph install operation, including both
        the graph comptutation and the binary installation.

        :param conanfile: ``Conanfile`` object representing the "root" node in the dependency graph,
          corresponding to a ``conanfile.py`` in the user folder, containing the ``build()`` method to
          be called. This ``conanfile`` object must have all of its dependencies computed and
          installed in the current Conan package cache to work.
        """
        hook_manager = self._helpers.hook_manager
        conanfile.folders.set_base_package(conanfile.folders.base_build)
        conanfile.folders.set_base_pkg_metadata(os.path.join(conanfile.build_folder, "metadata"))
        run_build_method(conanfile, hook_manager)

    @staticmethod
    def test(conanfile) -> None:
        """ Calls the ``test()`` method of the current (user folder) ``test_package/conanfile.py``

        This method does require computing a dependency graph, because the ``test()`` method
        needs all dependencies and transitive dependencies. Then, the ``conanfile`` argument
        must be the one obtaind from a full dependency graph install operation, including both
        the graph comptutation and the binary installation.

        Typically called after a ``build()`` one.

        :param conanfile: ``Conanfile`` object representing the "root" node in the dependency graph,
          corresponding to a conanfile.py in the user "test_package" folder, containing the ``test()``
          method to be called. This ``conanfile`` object must have all of its dependencies computed
          and installed in the current Conan package cache to work.
        """
        with conanfile_exception_formatter(conanfile, "test"):
            with chdir(conanfile.build_folder):
                conanfile.test()

    def inspect(self, conanfile_path, remotes, lockfile, name=None, version=None, user=None,
                channel=None):
        app = ConanApp(self._conan_api)
        conanfile = app.loader.load_named(conanfile_path, name=name, version=version, user=user,
                                          channel=channel, remotes=remotes, graph_lock=lockfile)
        return conanfile

    def reinit(self):
        self.editable_packages = EditablePackages(self._conan_api.home_folder)
