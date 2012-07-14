class PlayerBase(object):
    '''
    All player roles should extend this class. The inheritance hierarchy
    should be flat.
    '''
    def __init__(self, nick, game):
        self.nick = nick
        self.game = game

    def getRole(self):
        return self.__class__.__name__

    def getDescription(self):
        '''
        A complete message that the player should receive if they forget their
        own role and ask the bot for help.
        '''
        return ("I don't know what you are! This is a bug in kevinbot or " +
                "one of its modules. (Class %s)" % self.__class__.__name__)

# CORE ROLES
class Villager(PlayerBase):
    def __init__(self, nick, game):
        super(Villager, self).__init__(nick, game)

    def getDescription(self):
        return ('You are a villager. Typically, your kind makes up the bulk ' +
                'of the players at the beginning of the game. You have no ' +
                'special abilities, but you can vote just like all other ' +
                'players. You win when there are no mafia remaining.')

class Mafia(PlayerBase):
    def __init__(self, nick, game):
        super(Mafia, self).__init__(nick, game)

    def getDescription(self):
        return ('You are a member of the Mafia. Each night, you and your ' +
                'fellow mafiosi agree to kill one citizen. You win when all ' +
                'innocent citizens have been killed.')

# AUXILIARY ROLES
class Doctor(PlayerBase):
    def __init__(self, nick, game):
        super(Doctor, self).__init__(nick, game)

    def getDescription(self):
        return ('You are a doctor! Each night, you can choose one player to ' +
                'save. If the mafia choose to kill that player, they will ' +
                'not die.')

class Idiot(PlayerBase):
    def __init__(self, nick, game):
        super(Idiot, self).__init__(nick, game)

    def getDescription(self):
        return ('You are an idiot. You are just like an ordinary villager, ' +
                'but you can win only if you are executed by the village. ' +
                '(In this case, the villagers and the mafia both lose. If ' +
                'the village wins or you are killed by the mafia, you lose.')

class Inspector(PlayerBase):
    def __init__(self, nick, game):
        super(Inspector, self).__init__(nick, game)

    def getRole(self):
        return 'Detective' # for historical reasons

    def getDescription(self):
        return ('You are a detective! Each night, you can inspect any ' +
                'player (and you will learn whether or not they are sided ' +
                'with the mafia).')
