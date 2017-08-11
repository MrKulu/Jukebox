def execute(bot,parameter):
    if bot.randomize:
        bot.send_msg_channel("Next song will be chosen at random!")
    else:
        if bot.playlist.length() == 0:
            bot.send_msg_channel("The playlist is empty")
        else:
            nxt = bot.playlist[0]
            if nxt.title is not None:
                bot.send_msg_channel("Next song will be <b>%s</b>" % nxt.title)
            else:
                bot.send_msg_channel('Next song will be <a href="%s">%s</a>' % (nxt.url,nxt.url))