from io import StringIO
from typing import Tuple

from model.ref import ConanFileReference, PackageReference


class Cache:
    """ Interface for different cache implementations: single cache, two-level cache,... """

    def dump(self, output: StringIO):
        raise NotImplementedError

    """
    Methods for references
    """

    def get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        """ Returns the layout for a reference. The recipe revision is a requirement, only references
            with rrev are stored in the database.
        """
        assert ref.revision, "Ask for a reference layout only if the rrev is known"
        return self._get_reference_layout(ref)

    def _get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        raise NotImplementedError

    def get_or_create_reference_layout(self, ref: ConanFileReference) -> Tuple['RecipeLayout', bool]:
        raise NotImplementedError

    """
    Methods for packages
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

