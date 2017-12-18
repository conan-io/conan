
def defs_to_string(defs):
    return " ".join(['-D{0}="{1}"'.format(k, v) for k, v in defs.items()])


def join_arguments(args):
    return " ".join(filter(None, args))
