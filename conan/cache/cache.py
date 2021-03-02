from io import StringIO

from model.ref import ConanFileReference, PackageReference


class Cache:
    """ Interface for different cache implementations: single cache, two-level cache,... """

    def dump(self, output: StringIO):
        raise NotImplementedError

    def get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        raise NotImplementedError

    def get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        raise NotImplementedError
