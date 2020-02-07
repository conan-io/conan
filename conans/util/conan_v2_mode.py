import os
import warnings

from conans.errors import ConanV2Exception

CONAN_V2_MODE_ENVVAR = "CONAN_V2_MODE"


def conan_v2_behavior(msg, v1_behavior=warnings.warn):
    if os.environ.get(CONAN_V2_MODE_ENVVAR, False):
        msg = "Conan v2 incompatible: {}".format(msg)
        # TODO: Add a link to a public webpage with Conan roadmap to v2
        raise ConanV2Exception(msg)
    else:
        v1_behavior(message=msg, stacklevel=2)
