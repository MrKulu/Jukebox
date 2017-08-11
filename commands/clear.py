def execute(bot,parameter):
    bot.playlist = []
    bot.stop()
    ke = bot.downProc.keys()
    for i in ke:
        bot.downProc[i].terminate()
        bot.downProc[i].join()
        del bot.downProc[i]                