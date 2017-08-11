import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from Misc import get_url

def execute(bot,parameter):
    if parameter:
        options = parameter.split(' ')
        urlp = options.pop()
        bot.add_to_playlist(get_url(urlp), options = options+["add","hide"])