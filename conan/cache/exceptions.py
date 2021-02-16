from conans.errors import ConanException
from conans.model.ref import ConanFileReference, PackageReference


class DuplicateReferenceException(ConanException):
    def __init__(self, ref: ConanFileReference):
        msg = f"An entry for reference '{ref.full_str()}' already exists"
        super().__init__(msg)


class DuplicatePackageReferenceException(ConanException):
    def __init__(self, pref: PackageReference):
        msg = f"An entry for package reference '{pref.full_str()}' already exists"
        super().__init__(msg)
