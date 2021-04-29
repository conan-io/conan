def make_jobs_cmd_line_arg(conanfile):
    njobs = conanfile.conf["tools.gnu.make:jobs"] or \
            conanfile.conf["tools.build:processes"]
    if njobs:
        return "-j{}".format(njobs)
