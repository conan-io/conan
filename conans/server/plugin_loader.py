import os


def load_authentication_plugin(server_folder, plugin_name):
    try:
        from pluginbase import PluginBase
        plugin_base = PluginBase(package="plugins/authenticator")
        plugins_dir = os.path.join(server_folder, "plugins", "authenticator")
        plugin_source = plugin_base.make_plugin_source(
                        searchpath=[plugins_dir])
        auth = plugin_source.load_plugin(plugin_name).get_class()
        # it is necessary to keep a reference to the plugin, otherwise it is removed
        # and some imports fail
        auth.plugin_source = plugin_source
        return auth
    except Exception:
        print("Error loading authenticator plugin '%s'" % plugin_name)
        raise
