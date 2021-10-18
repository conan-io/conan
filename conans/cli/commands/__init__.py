from conans.errors import ConanException


def get_remote_selection(conan_api, args):
    remotes = []
    active_remotes = conan_api.remotes.list(only_active=True)
    if hasattr(args, "all_remotes") and args.all_remotes:
        remotes = active_remotes
    elif args.remote:
        active_remotes_names = [r.name for r in active_remotes]
        for arg in args.remote:
            if arg not in active_remotes_names:
                raise ConanException("The remote {} doesn't exist or it is disabled".format(arg))
    print(remotes)
    return remotes
