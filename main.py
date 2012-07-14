import json
import sys
from oyoyo.client import IRCClient
from constants import SETTINGS_FILE
from handler import KevinBotCommandHandler

# Main program
if __name__ == '__main__':
    try:
        f = open(SETTINGS_FILE, 'r')
        settings = json.load(f)
    except (IOError, ValueError):
        print >> sys.stderr,\
            ('File %s is missing or unreadable, or has an invalid format' %
             SETTINGS_FILE)
        exit(1)
    finally:
        f.close()
    # HACK: IRCClient.__init__ is expecting a class name that it can use to
    # construct a new handler object. This lambda expression allows us to
    # pass parameters to the handler's constructor, avoiding the need for
    # global variables.
    cli = IRCClient(lambda client: KevinBotCommandHandler(client, settings),
                    host = settings['host'],
                    port = settings['port'],
                    nick = settings['nick'],
                    blocking = True)
    conn = cli.connect()
    while True:
        conn.next()
    print 'Exiting.'
