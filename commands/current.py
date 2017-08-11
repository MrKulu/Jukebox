import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from LinkHandler import LinkHandler

def execute(bot,parameter):
    cur = LinkHandler.get_current()
    if cur is not None:
        if not bot.hidden and cur.title is not None and "hide" not in cur.options:
            bot.send_msg_channel('Currently playing <b>%s</b>' % (cur.title))
        else:
            bot.send_msg_channel('Currently playing <a href="%s">%s</a>' % (cur.url,cur.url))
    else:
        bot.send_msg_channel("Nothing is currently playing")