from constants import *
import roles
import random

class KevinBotArgumentException(Exception):
    pass

class KevinBotSettingException(Exception):
    pass

class KevinBotPermissionException(Exception):
    pass

class KevinBotGM:
    def __init__(self, commandHandler, channel):
        self.commandHandler = commandHandler
        self.channel = channel
        self.state = ST_INACTIVE
        self.users = {}
        self.players = {}
        self.my_nick = self.commandHandler.my_nick
        self.busy = 1
        self.send('JOIN', self.channel)

    def assignRoles(self):
        nPlayers = len(self.players)
        nDoctors = self.settings[OPT_NUM_DOCTORS]
        nInspectors = self.settings[OPT_NUM_INSPECTORS]
        nIdiots = self.settings[OPT_NUM_IDIOTS]
        nMafia = self.settings[OPT_NUM_MAFIA]
        auto = False
        if nMafia == NUM_MAFIA_AUTO1:
            nMafia = max(int((nPlayers - 2.0)/4.0), 1)
            auto = True
        nVillagers = nPlayers - nDoctors - nInspectors - nIdiots - nMafia
        if nVillagers < 0:
            self.echo('Cannot assign roles because there are more special ' +
                      'characters than there are players. For reference, ' +
                      'there are currently %d mafia and %d players' %
                      (nMafia, nPlayers))
            return False
        groups = self.random_partition(self.players.keys(),
                                       [nDoctors, nInspectors, nIdiots, nMafia,
                                        nVillagers])
        self.players.clear()
        for nick in groups[0]:
            self.players[nick] = roles.Doctor(nick, self)
        for nick in groups[1]:
            self.players[nick] = roles.Inspector(nick, self)
        for nick in groups[2]:
            self.players[nick] = roles.Idiot(nick, self)
        for nick in groups[3]:
            self.players[nick] = roles.Mafia(nick, self)
        for nick in groups[4]:
            self.players[nick] = roles.Villager(nick, self)
        for nick, player in self.players.items():
            self.privmsg(nick, 'Your role is %s' % player.getRole())
        self.echo('Roles have been assigned; check your private messages.')
        if auto:
            self.echo('Number of mafiosi: %d' % nMafia)
        return True

    def canStartGame(self):
        if not self.muted:
            return False
        for nick, mode in self.users.items():
            if nick == self.my_nick:
                if mode != '@':
                    return False
            else:
                if mode != ' ':
                    return False
        return True

    def checkDoctorsOver(self):
        for p in self.players.values():
            if p.__class__ == roles.Doctor and p.vote == None:
                return False
        self.startDay()
        return True

    def checkGameOver(self):
        # When there are as many mafia as villagers, the mafia win.
        bad = 0
        for player in self.players.values():
            if player.__class__ == roles.Mafia:
                bad += 1
        if bad == 0:
            self.echo('Game over---village wins.')
            self.endGame()
            return True
        else:
            good = len(self.players) - bad
            if bad >= good:
                self.echo('Game over---Mafia win.')
                self.endGame()
                return True
            else:
                return False

    def checkInspectorsOver(self):
        for p in self.players.values():
            if p.__class__ == roles.Inspector and p.vote == None:
                return False
        self.startNightDoctor()
        return True

    def checkMafiaOver(self):
        # We can assume there is at least one mafioso.
        target = None
        for p in self.players.values():
            if p.__class__ == roles.Mafia:
                if p.vote == None:
                    return False
                elif target == None:
                    target = p.vote
                elif target != p.vote:
                    return False
        self.victim = target
        self.mafiaBroadcast(None, '%s will be taken care of.' % target)
        self.startNightInspector()
        return True

    def checkVoteOver(self):
        '''
        If some or all votes have been counted and the difference between the
        leader and the runner-up is greater than the number of missing votes,
        the vote is over.
        If all votes have been counted and there is a tie, indicate this.
        '''
        N = len(self.players)
        votes = 0
        a = [set(self.players.keys())]
        for i in range(N):
            a.append(set())
        b = dict(zip(self.players.keys(), [0] * N))
        for p in self.players.values():
            if p.vote != None:
                a[b[p.vote]].discard(p.vote)
                b[p.vote] += 1
                a[b[p.vote]].add(p.vote)
                votes += 1
        target = None
        for i in range(N+1)[::-1]:
            if len(a[i]) == 0:
                continue
            if target == None:
                if len(a[i]) >= 2:
                    if votes == N:
                        self.echo('The vote is tied with the following ' +
                                  'leaders: ' + ', '.join(a[i]))
                    return False
                else: # exactly 1
                    target = a[i].pop()
            else:
                if b[target] - i > N - votes:
                    break
                else:
                    return False
        idiot = self.players[target].__class__ == roles.Idiot
        self.echo('%s (%s) has been lynched.' % (target,
                  self.players[target].getRole()))
        del self.players[target]
        self.mode('-v', target)
        if idiot:
            self.echo('Game over---Village Idiot wins.')
            self.endGame()
        elif not self.checkGameOver():
            self.startNightMafia()
        return True

    def echo(self, msg):
        '''Sends a notice to the channel'''
        self.send('NOTICE %s :%s' % (self.channel, msg))

    def endGame(self):
        self.mode('-m')
        self.state = ST_INACTIVE
        for p in self.players.values():
            self.echo('%s was %s!' % (p.nick, p.getRole()))

    def get(self, level, setting):
        setting = setting.lower()
        if setting in self.settings:
            return self.settings[setting]
        else:
            raise KevinBotSettingException()

    def getMode(self):
        self.busy += 1
        self.send('MODE', self.channel)

    def mafiaBroadcast(self, nick, msg):
        for p in self.players.values():
            if p.nick != nick and p.__class__ == roles.Mafia:
                self.privmsg(p.nick, msg)

    def mode(self, *args):
        self.send('MODE', self.channel, ' '.join(args))

    def privmsg(self, nick, msg):
        '''Sends a private message'''
        self.send('PRIVMSG %s :%s' % (nick, msg))

    def random_partition(self, values, counts):
        random.shuffle(values)
        ret = []
        for i in counts:
            ret.append(values[:i])
            values = values[i:]
        return ret

    def replyto(self, nick, msg, private = False):
        '''example: "brian: You can't do that!"'''
        if private:
            self.send('PRIVMSG %s :%s' % (nick, msg))
        else:
            self.send('PRIVMSG %s :%s: %s' % (self.channel, nick, msg))

    def resendNames(self):
        self.busy += 1
        self.users.clear()
        self.send('NAMES', self.channel)

    def send(self, *args):
        '''Sends a command directly through the IRC socket'''
        self.commandHandler.client.send(*args)

    def set(self, level, setting, value):
        setting = setting.lower()
        if not (setting in self.settings):
            raise KevinBotSettingException()
        elif level < LVL_OP:
            raise KevinBotPermissionException()
        # TODO (v1.1): refactor this
        elif setting == OPT_NUM_MAFIA and value == NUM_MAFIA_AUTO1:
            self.settings[setting] = value
        else:
            try:
                num = int(value)
                if num < 0 or num == 0 and setting == OPT_NUM_MAFIA:
                    raise KevinBotArgumentException()
                if num > 1 and setting == OPT_SELF_PROTECTING_DOCTOR:
                    raise KevinBotArgumentException()
                self.settings[setting] = num
            except ValueError:
                raise KevinBotArgumentException()

    def startDay(self):
        self.echo('It is now daytime.')
        self.state = ST_DAY
        self.voiceAll('+')
        saved = False
        for p in self.players.values():
            if p.__class__ == roles.Doctor and p.vote == self.victim:
                saved = True
        if saved:
            self.echo('Nobody was killed by the Mafia last night.')
        else:
            self.echo('%s (%s) was killed by the Mafia last night.' %
                        (self.victim, self.players[self.victim].getRole()))
            del self.players[self.victim]
            self.mode('-v', self.victim)
            if self.checkGameOver():
                return
        for p in self.players.values():
            p.vote = None

    def startGame(self):
        self.echo('Game started.')
        self.victim = None
        self.startNightMafia()

    def startNightDoctor(self):
        doctor_exists = False
        for p in self.players.values():
            if p.__class__ == roles.Doctor:
                p.vote = None
                doctor_exists = True
                self.privmsg(p.nick, 'Choose someone to save.')
                self.privmsg(p.nick, 'Type "SAVE <nick>" when you have ' +
                                     'chosen.')
        if doctor_exists:
            self.state = ST_NIGHT_DOCTOR
            self.echo('Still nighttime. Doctor(s) at work.')
        else:
            self.startDay()

    def startNightInspector(self):
        inspector_exists = False
        for p in self.players.values():
            if p.__class__ == roles.Inspector:
                p.vote = None
                inspector_exists = True
                self.privmsg(p.nick, 'Choose someone to inspect.')
                self.privmsg(p.nick, 'Type "INSPECT <nick>" when you have ' +
                                     'chosen.')
        if inspector_exists:
            self.state = ST_NIGHT_INSPECTOR
            self.echo('Still nighttime. Detective(s) at work.')
        else:
            self.startNightDoctor()

    def startNightMafia(self):
        self.echo('It is now nighttime, and the Mafia are afoot.')
        self.voiceAll('-')
        self.mafiaBroadcast(None, 'Tonight the Mafia will liquidate ' +
                                  'someone. Discuss whom.')
        self.mafiaBroadcast(None, 'Use "KILL <nick>" to select someone to ' +
                                  'kill. All messages will be CCed to all ' +
                                  'other mafiosi (if any). All mafiosi ' +
                                  'must select the same victim.')
        self.state = ST_NIGHT_MAFIA
        for p in self.players.values():
            if p.__class__ == roles.Mafia:
                p.vote = None

    def unexpectedDeathTriggers(self, nick):
        self.mode('-v', nick)
        # This is called AFTER the player has been destroyed.
        if self.checkGameOver():
            return
        # If it's the day phase, check whether everyone has voted.
        if self.state == ST_DAY:
            for p in self.players.values():
                if p.vote == nick:
                    self.replyto(p.nick, 'Your vote is no longer valid.')
                    p.vote = None
            self.checkVoteOver()
        elif self.state == ST_NIGHT_MAFIA:
            for p in self.players.values():
                if p.__class__ == roles.Mafia and p.vote == nick:
                    self.mafiaBroadcast(None, "%s' vote is no longer valid"\
                                              % p.nick)
                    p.vote = None
            self.checkMafiaOver()
        elif self.state == ST_NIGHT_DOCTOR:
            self.checkDoctorsOver()
        elif self.state == ST_NIGHT_INSPECTOR:
            self.checkInspectorsOver()

    def userlevel(self, nick):
        '''Gets the privilege level of the user.'''
        if nick in self.commandHandler.settings['admins']:
            return LVL_ADMIN
        elif nick == self.creator:
            return LVL_OP
        else:
            return LVL_LUSER

    def voiceAll(self, sign):
        buf = []
        bufSize = 0
        for nick in self.players:
            if bufSize + len(nick) + 2 > 400 or len(buf) >= 3:
                self.voiceAllHelper(buf, sign)
                bufSize = 0
                buf = []
            bufSize += len(nick) + 2
            buf.append(nick)
        self.voiceAllHelper(buf, sign)

    def voiceAllHelper(self, buf, sign):
        self.mode(sign + len(buf)*'v', *buf)

    def _chanmsg(self, nick, msg):
        '''Called when a message is posted to this channel.'''
        if self.busy:
            return
        if not msg.startswith('!'):
            return
        words = msg.split()
        # words must have at least one entry, since msg starts with !
        # and that first entry must have at least one character
        cmd = words[0][1:]
        if (not cmd.startswith('_') and
            callable(getattr(self, 'c_' + cmd, None))):
            self.is_private_command = False
            try:
                getattr(self, 'c_' + cmd)(nick, *words[1:])
            except KevinBotArgumentException:
                self.replyto(nick, 'Invalid arguments to !%s' % cmd)
        else:
            self.replyto(nick, 'Invalid command !%s' % cmd)

    def _cmode(self, modestr):
        if 'm' in modestr:
            self.muted = True
        else:
            self.muted = False
        self.busy -= 1
        if self.state == ST_PENDING_MODES and self.canStartGame():
            self.startGame()

    def _endofnames(self):
        self.busy -= 1
        if self.state == ST_PENDING_MODES and self.canStartGame():
            self.startGame()

    def _join(self, nick):
        if nick == self.my_nick:
            self.echo(VERSION)
            self.echo('To create a game, type !create')
            self.getMode()
        else:
            self.users[nick] = ' '

    def _kick(self, nick):
        del self.users[nick]

    def _mode(self, modestr, *args):
        # The information I found online is unclear on whether modern IRCds
        # always send 005 RPL_ISUPPORT, which we ideally want in order to
        # be able to properly parse mode strings. So I will just re-issue
        # NAMES every time anything changes. This is less performant but
        # also much simpler.
        if 'o' in modestr or 'h' in modestr or 'v' in modestr:
            self.resendNames()
        if 'm' in modestr:
            self.getMode()

    def _namreply(self, users):
        self.users.update(users) # Python awwww yeahhhh

    def _nick(self, oldnick, newnick):
        if oldnick == self.my_nick:
            self.my_nick = newnick
        self.users[newnick] = self.users[oldnick]
        del self.users[oldnick]

    def _part(self, nick):
        del self.users[nick]

    def _quit(self, nick):
        del self.users[nick]

    def _usermsg(self, nick, msg):
        '''
        There are only three in-game commands that need to be accepted in
        private messages as well as channel messages. The reason for this is
        that a player might want to perform them at any time, even if it is
        night and they have no voice:
          !abort: ends the game
          !kick: removes another player from the game
          !quit: removes yourself from the game
        Also, the command !role should always be private-messaged, because the
        reply will always be a private message.
        The command !list was added due to beta test feedback.
        '''
        if self.busy:
            return
        words = msg.split()
        if len(words) == 0:
            return
        if words[0] in ['!abort', '!kick', '!quit', '!role', '!list']:
            self.is_private_command = True
            try:
                getattr(self, 'c_' + words[0][1:])(nick, *words[1:])
            except KevinBotArgumentException():
                self.privmsg(nick, 'Invalid arguments to !%s' % words[0][1:])
        elif self.state == ST_NIGHT_MAFIA:
            # Already know player is in game, don't check again
            if self.players[nick].__class__ == roles.Mafia:
                self.mafiaBroadcast(nick, '<%s> %s' % (nick, msg))
            else:
                return
            # Check whether this is a vote.
            if len(words) == 2 and words[0] == 'KILL':
                if words[1] in self.players:
                    self.players[nick].vote = words[1]
                    self.checkMafiaOver()
                else:
                    self.mafiaBroadcast(None, 'No such player %s' % words[1])
        elif self.state == ST_NIGHT_INSPECTOR:
            if self.players[nick].__class__ != roles.Inspector:
                return
            if len(words) == 2 and words[0] == 'INSPECT':
                if self.players[nick].vote:
                    self.privmsg(nick, 'You can only inspect one player per ' +
                                       'night.')
                    return
                target = words[1]
                if target in self.players:
                    self.players[nick].vote = target
                    if self.players[target].__class__ == roles.Mafia:
                        self.privmsg(nick, 'Mafia')
                    else:
                        self.privmsg(nick, 'Innocent')
                    self.checkInspectorsOver()
                else:
                    self.privmsg(nick, 'No such player.')
        elif self.state == ST_NIGHT_DOCTOR:
            if self.players[nick].__class__ != roles.Doctor:
                return
            if len(words) == 2 and words[0] == 'SAVE':
                target = words[1]
                if (target == nick and
                    not self.settings[OPT_SELF_PROTECTING_DOCTOR]):
                    self.privmsg(nick, 'You cannot save yourself.')
                elif target in self.players:
                    self.players[nick].vote = target
                    self.privmsg(nick, 'You have chosen to save %s'\
                                       % target)
                    self.checkDoctorsOver()
                else:
                    self.privmsg(nick, 'No such player.')

    def c_abort(self, nick, *args):
        '''Abort the game in progress'''
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.', self.is_private_command)
        elif self.userlevel(nick) < LVL_OP:
            self.replyto(nick, 'Not authorized.', self.is_private_command)
        elif self.state == ST_WAITING_FOR_PLAYERS:
            self.replyto(nick, 'The game has not yet started.',
                         self.is_private_command)
        else:
            self.echo('Game aborted by %s' % nick)
            self.endGame()

    def c_create(self, nick, *args):
        '''Create a new game'''
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.state = ST_WAITING_FOR_PLAYERS
            self.players = {}
            self.settings = {OPT_NUM_DOCTORS: 1,
                             OPT_NUM_INSPECTORS: 1,
                             OPT_NUM_IDIOTS: 0,
                             OPT_NUM_MAFIA: NUM_MAFIA_AUTO1,
                             OPT_SELF_PROTECTING_DOCTOR: 1}
            self.creator = nick
            self.echo('Game created by %s' % nick)
        else:
            self.replyto(nick, 'A game has already been created.')

    def c_cancel(self, nick, *args):
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.')
        elif self.state == ST_WAITING_FOR_PLAYERS:
            if self.userlevel(nick) >= LVL_OP:
                self.state = ST_INACTIVE
                self.echo('Game cancelled.')
            else:
                self.replyto(nick, 'You are not the creator of this game, ' +
                                   'so you cannot cancel it.')
        else:
            self.replyto(nick, 'Cannot cancel a game that has already ' +
                               'started. Maybe you meant to !abort.')

    def c_get(self, nick, *args):
        if len(args) != 1:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.')
            return
        setting = args[0]
        try:
            val = self.get(self.userlevel(nick), setting)
            self.replyto(nick, '%s = %s' % (setting, str(val)))
        except KevinBotSettingException:
            self.replyto(nick, 'Nonexistent setting %s' % setting)

    def c_join(self, nick, *args):
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_WAITING_FOR_PLAYERS:
            if nick in self.players:
                self.replyto(nick, 'You are already in this game.')
            else:
                can_join = True
                for chan, game in self.commandHandler.channels.items():
                    if chan != self.channel and nick in game.players:
                        can_join = False
                if can_join:
                    self.players[nick] = None
                    self.echo('%s has joined the game.' % nick)
                else:
                    self.replyto(nick, 'You can only be in one game at a ' +
                                       'time.')
        elif self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game to join.')
        else:
            self.replyto(nick, 'The game has already started.')

    def c_list(self, nick, *args):
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.', self.is_private_command)
        else:
            self.replyto(nick, ', '.join(self.players.keys()),
                         self.is_private_command)

    def c_kick(self, nick, *args):
        if len(args) != 1:
            raise KevinBotArgumentException()
        target = args[0]
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.', self.is_private_command)
        elif self.userlevel(nick) < LVL_OP:
            self.replyto(nick, 'Only the game creator can kick players.',
                         self.is_private_command)
        elif self.state == ST_WAITING_FOR_PLAYERS:
            self.replyto(nick, 'Use !remove to remove a player from the ' +
                               'tentative game.', self.is_private_command)
        elif target in self.players:
            self.echo('%s (%s) was kicked by %s' % (target,
                        self.players[target].getRole(), nick))
            del self.players[target]
            self.unexpectedDeathTriggers(target)
        else:
            self.replyto(nick, '%s is not in this game' % target,
                         self.is_private_command)

    def c_quit(self, nick, *args):
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.', self.is_private_command)
        elif self.state == ST_WAITING_FOR_PLAYERS:
            self.replyto(nick, 'The game has not yet started.',
                         self.is_private_command)
        elif not (nick in self.players):
            self.replyto(nick, 'You are not in this game.',
                         self.is_private_command)
        else:
            self.echo('%s (%s) has quit.' %
                        (nick, self.players[nick].getRole()))
            del self.players[nick]
            self.unexpectedDeathTriggers(nick)

    def c_remove(self, nick, *args):
        if len(args) != 1:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.')
        elif self.userlevel(nick) < LVL_OP:
            self.replyto(nick, 'Not authorized!')
        elif self.state == ST_WAITING_FOR_PLAYERS:
            if args[0] in self.players:
                del self.players[args[0]]
                self.echo('%s removed %s from the game.' % (nick, args[0]))
            else:
                self.replyto(nick, '%s is not in the game.' % args[0])
        else:
            self.replyto(nick, 'Use !kick to remove a player after the game ' +
                               'has already started.')

    def c_role(self, nick, *args):
        if not self.is_private_command:
            return
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.privmsg(nick, 'No active game.')
        elif self.state == ST_WAITING_FOR_PLAYERS:
            self.privmsg(nick, 'The game has not yet started.')
        elif nick in self.players:
            self.privmsg(nick, self.players[nick].getDescription())
        else:
            self.privmsg(nick, 'You are not in the game.')

    def c_set(self, nick, *args):
        if len(args) != 2:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'No active game.')
            return
        setting = args[0]
        val = args[1]
        try:
            self.set(self.userlevel(nick), setting, val)
            self.echo('%s set %s = %s' % (nick, setting, val))
        except KevinBotArgumentException:
            self.replyto(nick, 'Invalid value %s for %s' % (val, setting))
        except KevinBotPermissionException:
            self.replyto(nick, "You don't have permission to set %s = %s" %
                               (setting, val))
        except KevinBotSettingException:
            self.replyto(nick, 'Nonexistent setting %s' % setting)

    def c_start(self, nick, *args):
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_INACTIVE:
            self.replyto(nick, 'You must create a game first.')
        elif self.state == ST_WAITING_FOR_PLAYERS:
            if self.userlevel(nick) >= LVL_OP:
                if self.users[self.my_nick] != '@':
                    self.replyto(nick,
                                 '%s needs operator status in order to run.' %
                                 self.my_nick)
                else:
                    if self.assignRoles():
                        if self.canStartGame():
                            self.startGame()
                        else:
                            self.state = ST_PENDING_MODES
                            self.echo('The game will start as soon as the ' +
                                      'appropriate modes have been set.')
                            if not self.muted:
                                self.mode('+m')
                            for nick, mode in self.users.items():
                                if nick != self.my_nick and mode != ' ':
                                    self.mode('-ohv', nick, nick, nick)
            else:
                self.replyto(nick, 'Only the game creator can start the game.')
        else:
            self.replyto(nick, 'The game has already started.')

    def c_unjoin(self, nick, *args):
        if len(args) > 0:
            raise KevinBotArgumentException()
        if self.state == ST_WAITING_FOR_PLAYERS:
            if nick in self.players:
                del self.players[nick]
                self.replyto(nick, 'You are no longer in the game.')
            else:
                self.replyto(nick, 'You are not in this game.')
        elif self.state == ST_INACTIVE:
            self.replyto(nick, 'No current game.')
        else:
            self.replyto(nick,
                    'You cannot unjoin a game that has already started. ' +
                    'Perhaps you meant to !quit the game that is in ' +
                    'progress.')

    def c_vote(self, nick, *args):
        if len(args) > 1:
            raise KevinBotArgumentException()
        if self.state == ST_DAY:
            if nick in self.players:
                if args[0] in self.players:
                    self.replyto(nick, 'Your vote has been registered.')
                    self.players[nick].vote = args[0]
                    self.checkVoteOver()
                else:
                    self.replyto(nick, 'No such player %s' % args[0])
            else:
                self.replyto(nick, 'You are not in the game.')
        else:
            self.replyto(nick, 'You can only vote during the day.')

