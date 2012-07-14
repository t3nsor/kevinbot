import signal
from oyoyo.cmdhandler import DefaultCommandHandler
from oyoyo import helpers
from constants import VERSION, HELP_URL
from kevinbot import KevinBotGM

class KevinBotCommandHandler(DefaultCommandHandler):
    def __init__(self, client, settings):
        self.client = client
        self.settings = settings
        self.my_nick = self.settings['nick']
        self.users = {} # users[association.
        self.channels = {} # This stores the channel->game association.
        self.busy = 1 # Wait for RPL_WELCOME.
        for chan in self.settings['channels']:
            self.channels[chan] = None
        for i in range(1, signal.NSIG):
            try:
                signal.signal(i, lambda *args: self.__sighandler(*args))
            except RuntimeError:
                pass

    def __sighandler(self, signalnum, *args):
        for chan in self.channels:
            self.client.send('MODE %s -m' % chan)
        self.client.send('QUIT :Caught signal %d' % signalnum)
        exit(1)

    def channelmodeis(self, host, nick, chan, modestr, *args):
        self.channels[chan]._cmode(modestr)

    def endofnames(self, host, nick, chan, msg):
        self.channels[chan]._endofnames()

    def invite(self, nickhost, target, chan):
        if target == self.my_nick and not chan in self.channels:
            self.channels[chan] = KevinBotGM(self, chan)
        else:
            pass # can this even happen?

    def join(self, nickhost, chan):
        nick, host = nickhost.split('!')
        self.channels[chan]._join(nick) # Delegate

    def kick(self, nickhost, chan, target, msg):
        if target == self.my_nick:
            del self.channels[chan]
        else:
            self.channels[chan]._kick(nick)

    '''
    You may notice there is no kill handler. This is because when other users
    get killed, we see it as a quit, but when we get killed, there is no point
    in trying to continue anyway.
    '''

    def mode(self, nickhost, target, modestr, *args):
        if target != self.my_nick: # Ignore user modes.
            self.channels[target]._mode(modestr, *args)

    def namreply(self, host, nick, chanmode, chan, users):
        nice = []
        for user in users.split():
            mode = ' '
            if user[0] in '@%+':
                mode, user = user[0], user[1:]
            nice.append((user, mode))
        self.channels[chan]._namreply(nice) # delegate

    def nick(self, origin, newnick):
        oldnick, host = origin.split('!')
        # If this is us, it means a nick change was forced
        if oldnick == self.my_nick:
            self.my_nick = newnick
        # Propagate this change to all channels.
        for chan in self.channels:
            self.channels[chan]._nick(oldnick, newnick)

    def part(self, nickhost, chan, *args):
        nick, host = nickhost.split('!')
        self.channels[chan]._part(nick)

    def privmsg(self, nickhost, chan, msg):
        if self.busy:
            return
        nick, host = nickhost.split('!')
        if chan == self.my_nick: # user private message
            # Always respond to !version, !help directly
            if msg == '!version':
                helpers.msg(self.client, nick, VERSION)
            elif msg == '!help' or msg.startswith('!help '):
                helpers.msg(self.client, nick, HELP_URL)
            else:
                # The !abort and !kick commands require a channel argument.
                # The !quit and !role commands do not.
                args = msg.split()
                if len(args) == 0:
                    return
                if args[0] == '!abort' or args[0] == '!kick':
                    if len(args) >= 2:
                        if args[1] in self.channels:
                            self.channels[args[1]]._usermsg(
                              nick, ' '.join([args[0]] + args[2:])
                            )
                        else:
                            helpers.msg(
                              self.client,
                              nick,
                              'Channel %s does not exist!' % args[1]
                            )
                else:
                    for game in self.channels.values():
                        if nick in game.players:
                            game._usermsg(nick, msg)
        else: # channel message; dispatch to appropriate GM
            self.channels[chan]._chanmsg(nick, msg)

    def quit(self, nickhost, msg, *args):
        nick, host = nickhost.split('!')
        for chan in self.channels:
            self.channels[chan]._quit(nick)

    def welcome(self, *args):
        '''Wait for the RPL_WELCOME before joining channels.'''
        self.busy -= 1
        # We don't really care whether this succeeds.
        helpers.ns(self.client, 'IDENTIFY', self.settings['password'])
        for chan in self.channels:
            self.channels[chan] = KevinBotGM(self, chan)
