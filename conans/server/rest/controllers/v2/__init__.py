from conans.model.ref import ConanFileReference, PackageReference


def get_package_ref(name, version, username, channel, package_id, revision, p_revision):
    ref = ConanFileReference(name, version, username, channel, revision)
    package_id = "%s#%s" % (package_id, p_revision) if p_revision else package_id
    return PackageReference(ref, package_id)
