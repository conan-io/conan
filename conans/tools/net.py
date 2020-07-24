from conans.client.tools import net as tools_net

ftp_download = tools_net.ftp_download


def download(conanfile, *args, **kwargs):
    return tools_net.download(out=conanfile.output, requester=conanfile.requester, config=conanfile.config, *args, **kwargs)


def get(conanfile, *args, **kwargs):
    return tools_net.get(output=conanfile.output, requester=conanfile.requester, *args, **kwargs)
