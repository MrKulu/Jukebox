def execute(bot,parameter):
    bot.randomize = not bot.randomize
    if bot.randomize:
        bot.send_msg_channel("Randomizer On")
        bot.log.debug('Randomizer On')
    else:
        bot.send_msg_channel("Randomizer Off")
        bot.log.debug('Randomizer Off')