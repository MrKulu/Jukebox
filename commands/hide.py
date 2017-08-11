def execute(bot,parameter):
    bot.hidden = not bot.hidden
    if bot.hidden:
        bot.send_msg_channel("Hide mode On")
        bot.log.debug('Hide mode On')
    else:
        bot.send_msg_channel("Hide mode Off")
        bot.log.debug('Hide mode Off')