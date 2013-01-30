from ZomgBot.topo_sort import recursive_sort, free

import imp
import inspect
import os
from os import path
from glob import glob
from functools import wraps


class PluginManager(object):
    """
    Manage plugin loading and dependency resolution
    """
    plugins = {}
    instances = {}

    instance = None

    def __init__(self, parent):
        self.parent = parent
        self.events = parent.events
        PluginManager.instance = self

    def load_plugins(self, package="ZomgBot.plugins"):
        modpath = path.join(os.curdir, *package.split('.') + ['*.py'])
        for mod in glob(modpath):
            if path.basename(mod).startswith("__init__."): continue
            m = imp.load_source(path.splitext(path.basename(mod))[0], mod)
        self.ordered_enable(*self.parent.config["bot"]["plugins"])
        self.events.dispatchEvent(name="PluginsLoaded", event=None)
        print self.instances

    def get_plugin(self, plugin_name):
        if self.plugins.has_key(plugin_name):
            if self.instances.has_key(self.plugins[plugin_name]):
                return self.instances[self.plugins[plugin_name]]
        return None

    def enable(self, plugin):
        plugin = self.plugins[plugin]
        self.instances[plugin] = plugin(self)
        self.instances[plugin].setup()

    def disableAll(self):
        for p in self.instances.values():
            self.disable(p)
        self.instances = {}

    def disable(self, plugin):
        if isinstance(plugin, basestring):
            return self.disable(self.plugins[plugin])
        print plugin
        plugin.teardown()
        self.events.unregisterHandlers(plugin.__class__)
        del self.plugins[plugin.name]

    def ordered_enable(self, *plugins):
        nodes = [(plugin.name, tuple(plugin.plugin_info["depends"] or [])) for plugin in self.plugins.values()]
        order = recursive_sort(nodes, set((plugin, d) for plugin, d in free(nodes) if self.plugins[plugin].name in plugins))
        print "{}: Resolved plugin load order: {}".format(plugins, ', '.join(order))
        for p in order:
            self.enable(p)


class Plugin(object):
    """
    Base class for all plugins
    """
    def __init__(self, parent):
        self.events = parent.events
        self.parent = parent

        for m in dict(inspect.getmembers(self, inspect.ismethod)).values():
            if not hasattr(m.__func__, "event"): continue # not an event handler
            for event, priority in m.__func__.event:
                PluginManager.instance.events.addEventHandler(m.__func__.plugin, event, m, priority=priority)

    @staticmethod
    def register(depends=None):
        def inner(cls):
            cls.name = cls.__module__.split(".")[-1]
            cls.plugin_info = {"depends": depends}
            PluginManager.instance.plugins[cls.name] = cls

            # handle tags we may have left in decorators
            for m in dict(inspect.getmembers(cls, inspect.ismethod)).values():
                if not hasattr(m.__func__, "plugin"): continue  # we don't care
                m.__func__.plugin = cls
                
        return inner

    def setup(self):
        pass

    def teardown(self):
        pass

    def get_config(self):
        cfg = self.parent.parent.config
        cfg.setdefault("plugins", {})
        return cfg["plugins"].setdefault(self.name, {})

    def save_config(self):
        self.parent.parent.config.save()


class _Annotation(object):
    def __init__(self):
        self.all = {}

    def get(self, k):
        return [fn for fn in self.all.get(k, []) if fn.plugin in PluginManager.instance.instances]
    
    def get_by_name(self, k):
        return dict((fn.__name__, fn) for fn in self.get(k))

    def forgetPlugin(self, plugin):
        self.all = dict((k, [f for f in v if f.plugin != plugin]) for k, v in self.all)

    def forgetEverything(self):
        self.all = {}

    def __getattr__(self, k):
        def wrapper(*args, **kwargs):
            kwargs["args"] = args
            def inner(fn):
                @wraps(fn)
                def cc(*args, **kwargs):
                    return fn(PluginManager.instance.instances[fn.plugin], *args, **kwargs)
                self.all.setdefault(k, [])
                self.all[k].append(fn)
                fn.annotation = getattr(fn, "annotation", {})
                fn.annotation[k] = kwargs
                fn.plugin = None
                fn.call_with_self = cc
                return fn
            return inner
        return wrapper


Modifier = _Annotation()
