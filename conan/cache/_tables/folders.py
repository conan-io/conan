from enum import Enum, unique

from conan.cache._tables.base_table import BaseTable


@unique
class ConanFolders(Enum):
    REFERENCE = 0
    PKG_BUILD = 1
    PKG_PACKAGE = 2


class Folders(BaseTable):
    table_name = 'conan_paths'
    columns_description = [('reference_pk', int),
                           ('package_pk', int, True),
                           ('path', str),
                           ('folder', int, False, list(map(int, ConanFolders))),
                           ('last_modified', int)]
