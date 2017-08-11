def execute(bot,parameter):
    if parameter is not None and parameter.isdigit() and int(parameter) >= 0 and int(parameter) <= 100:
        bot.volume = float(float(parameter) / 100)
        bot.send_msg_channel("Volume has been set to " + str(int(bot.volume*100)))
        bot.set_comment_info()
    else:
        bot.send_msg_channel("Current volume is " + str(int(bot.volume*100)))