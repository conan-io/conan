from conan.api.output import ConanOutput
from conan.api.model import PkgReference as _PkgReference

_msg = """
*******************************************************************
Private '{}'
detected in user code (custom commands, extensions, recipes, etc).
Please stop using it, use only public documented APIs, , such as
'from conan.api.model import PkgReference'
as this will break in next releases.
*******************************************************************
"""


class PkgReference(_PkgReference):
    usage_counter = 0

    def __init__(self, *args, **kwargs):
        if PkgReference.usage_counter == 0:
            ConanOutput().warning(_msg.format("from conans.model.package_ref import PkgReference"))
        PkgReference.usage_counter += 1
        super(PkgReference, self).__init__(*args, **kwargs)

    @staticmethod
    def loads(*args, **kwargs):
        if PkgReference.usage_counter == 0:
            ConanOutput().warning(_msg.format("from conans.model.package_ref import PkgReference"),
                                  warn_tag="deprecated")
        PkgReference.usage_counter += 1
        return _PkgReference.loads(*args, **kwargs)
