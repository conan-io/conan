from .generic import QbsGenericToolchain


def QbsToolchain(conanfile, **kwargs):
    return QbsGenericToolchain(conanfile, **kwargs)
