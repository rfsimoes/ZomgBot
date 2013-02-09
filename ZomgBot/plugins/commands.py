from ZomgBot.plugins import Plugin, Modifier
from ZomgBot.events import Event, EventHandler
import logging

class CommandContext(object):
    def __init__(self, user, channel):
        self.user = user
        self.channel = channel

    def reply(self, msg, public=True):
        if self.channel and public:
            self.channel.say(msg)
        else:
            self.user.say(msg)
    
    def parse_args(self, msg):
        self.args = msg[1:].split(' ')
        return self.args.pop(0)

@Plugin.register(depends=["auth", "permission"])
class Commands(Plugin):
    prefix = "/"

    def setup(self):
        if "prefix" in self.get_config():
            self.prefix = self.get_config()["prefix"]

    @EventHandler("PluginsLoaded")
    def on_PluginsLoaded(self, event):
        cmds = Modifier.get("command")
        self.commands = {}
        for cmd in cmds:
            a = cmd.annotation["command"]
            [self.commands.update({n: (cmd, a)}) for n in a.get("aliases", []) + [a["args"][0]]]
        print self.commands

    def _really_do_command(self, auth_result, name, context):
        if name in self.commands:
            cmd, an = self.commands[name]
            perm = an.get("permission")
            if not perm or context.user.has_permission(perm):
                try:
                    self.commands[name][0].call_with_self(context)
                except Exception as e:
                    logging.exception("Encountered a {} (\"{}\") executing /{}. Tell its retarded author to fix their shit.".format(e.__class__.__name__, str(e), name))
                    context.reply("Encountered a {} (\"{}\") executing /{}. Tell its retarded author to fix their shit.".format(e.__class__.__name__, str(e), name))
            else:
                context.reply("You need the permission {} and you don't have it, you fuckwad.".format(perm))
        else:
            context.reply("No such command, try another one you retard.")

    def do_command(self, name, context):
        print "Trying to execute {}".format(name)
        r = self.events.dispatchEvent(name="AuthenticateUser", event=Event(user=context.user.user, irc=context.user.irc))
        r.addCallback(self._really_do_command, name, context)

    @EventHandler("ChannelMsg")
    def handle_commands(self, event):
        if not event.message.startswith(self.prefix): return
        context = CommandContext(event.user, event.channel)
        command = context.parse_args(event.message)
        self.do_command(command, context)

    @EventHandler("PrivateMsg")
    def handle_private(self, event):
        if not event.message.startswith(self.prefix): return
        context = CommandContext(event.user, None)
        command = context.parse_args(event.message)
        self.do_command(command, context)

    @Modifier.command("mystatus")
    def cmd_mystatus(self, context):
        userhost = str(context.user)
        if context.user.hostname:
            userhost += "!{}@{}".format(context.user.username, context.user.hostname)
        context.reply("You are {}, ".format(userhost) + ("logged in as {}".format(context.user.account) if context.user.account else "not logged in"))
        # figure out human names for all their modes
        mnames = ', '.join(self.parent.parent.irc.statuses[s] for s in context.user.status)
        if mnames: context.reply("You are {} in {}".format(mnames, context.channel))

    @Modifier.command("reload")
    def cmd_reload(self, context):
        self.parent.parent.reload()

    @Modifier.command("rehash")
    def cmd_rehash(self, context):
        self.parent.parent.config.loadOrCreate()
        context.reply("Reloaded the configuration file")
