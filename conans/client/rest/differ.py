

def diff_snapshots(snap_origin, snap_dest):
    """
    Returns the diff of snapshots
    new: Means the files to be created in destination
    modified: Means the files to be copied again in destination
    deleted: Means the files that has to be deleted in destination
    """

    new = []
    modified = []

    for filename, md5_origin in snap_origin.items():
        if filename not in snap_dest:
            new.append(filename)
        else:
            if md5_origin != snap_dest[filename]:
                modified.append(filename)

    deleted = []

    for filename in list(snap_dest.keys()):
        if filename not in snap_origin:
            deleted.append(filename)

    return new, modified, deleted
