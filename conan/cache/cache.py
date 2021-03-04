from io import StringIO
from typing import Tuple, Iterator

from model.ref import ConanFileReference, PackageReference


class Cache:
    """ Interface for different cache implementations: single cache, two-level cache,... """

    def dump(self, output: StringIO):
        """ Dump the content of the cache in a human-readable format, only for debugging purposes """
        raise NotImplementedError

    # <editor-fold desc="Methods for references">
    def list_references(self, only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        """ Returns an iterator to all the references inside cache. The argument 'only_latest_rrev'
            can be used to filter and return only the latest recipe revision for each reference.
        """
        raise NotImplementedError

    def search_references(self, pattern: str,
                          only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        """ Returns an iterator to all the references matching the pattern given. The pattern is
            checked against the references full name using SQL LIKE functionality. The argument
            'only_latest_rrev' can be used to filter and return only the latest recipe revision for
            the matching references.
        """
        raise NotImplementedError

    def list_reference_versions(self, ref: ConanFileReference,
                                only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        """ Returns an iterator to all the references with the same 'ref.name' as the one provided.
            The argument 'only_latest_rrev' can be used to filter and return only the latest recipe
            revision for each of them.
        """
        raise NotImplementedError

    def get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        """ Returns the layout for a reference. The recipe revision is a requirement, only references
            with rrev are stored in the database. If it doesn't exists, it will raise
            References.DoesNotExist exception.
        """
        assert ref.revision, "Ask for a reference layout only if the rrev is known"
        return self._get_reference_layout(ref)

    def _get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        raise NotImplementedError

    def get_or_create_reference_layout(self, ref: ConanFileReference) -> Tuple['RecipeLayout', bool]:
        raise NotImplementedError

    # </editor-fold>

    # <editor-fold desc="Methods for packages">

    """
    def list_packages(self, ref: ConanFileReference,
                      only_latest_prev: bool) -> List[PackageReference]:
        raise NotImplementedError

    def get_package_layout_latest(self, pref: PackageReference) -> 'PackageLayout':
        raise NotImplementedError
    """

    def get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        """ Returns the layout for a package. The recipe revision and the package revision are a
            requirement, only packages with rrev and prev are stored in the database.
        """
        assert pref.ref.revision, "Ask for a package layout only if the rrev is known"
        assert pref.revision, "Ask for a package layout only if the prev is known"
        return self._get_package_layout(pref)

    def _get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        raise NotImplementedError

    def get_or_create_package_layout(self, pref: PackageReference) -> Tuple['PackageLayout', bool]:
        assert pref.ref.revision, "Ask for a package layout only if the rrev is known"
        raise NotImplementedError

    # </editor-fold>
