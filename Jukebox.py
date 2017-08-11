# -*- coding: utf-8 -*-

import httplib2
import os
import sys
import random
import string
import time
import re
import math
import sqlite3
import audioop
import hashlib
import argparse
import logging
import json
from codecs import open
from shutil import copyfile
from multiprocessing import Process
import subprocess as sp
import ConfigParser
import StringIO
import urllib2
import base64
import re
try:
    import ImageFile
    import Image
except ImportError:
    from PIL import ImageFile
    from PIL import Image
    
from commands import *

from LinkHandler import *

from Misc import *

sys.path.append(os.path.join(os.path.dirname(__file__), "pymumble"))
import pymumble

VERSION = "0.3b6"

class Jukebox:
    def __init__(self, host, user="Jukebox", port=64738, password="", channel="", config=None):

        self.playing = False
        self.url = None
        self.exit = False
        self.nbexit = 0

        try:
            self.volume = config.get("Bot","volume")
        except:
            self.volume = 0.5
        try:
            self.n_download = config.get("Bot","download")
        except:
            self.n_download = 1
        self.downProc = {}
        self.randomize = False
        self.hidden = False
        self.playlist = []
        
        self.log = logging.getLogger(__name__)

        self.mumble = pymumble.Mumble(host, user=user, port=port, password=password, reconnect=True,
                                      debug=False)
        self.mumble.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.message_received)

        self.mumble.start()  # start the mumble thread
        self.mumble.is_ready()  # wait for the connection
        self.mumble.users.myself.unmute()  # make sure the user is not muted
        self.set_comment_info()
        if channel != "":
            self.mumble.channels.find_by_name(channel).move_in()
        self.mumble.set_bandwidth(200000)
        self.loop()

    def set_comment_info(self):
        r = "Volume: "+str(self.volume)+ " || "
        u = LinkHandler.get_current()
        if u == None:
            r += "Idle"
        else:
            if not self.hidden and u.title is not None:
                r += "Playing " + u.title
            else:
                r += "Playing " + u.url
        self.mumble.users.myself.comment(r)
        
            
    def add_to_playlist(self, url, options=[]):
        if url.startswith("http"):
            batchfile = "~/.musiccache/%s.batch" % (hashlib.sha1(url).hexdigest())
            try:
                os.remove(os.path.expanduser(batchfile))
            except:
                True
            command = 'youtube-dl -4 --no-warnings --no-playlist --flat-playlist --dump-single-json %s >> %s' % (url,batchfile)
            sp.call(command, shell = True)
            f = open(os.path.expanduser(batchfile))
            try:
                fl = json.load(f)
            except:
                self.send_msg_channel('Invalid link <a href="%s">%s</a>'%(url,url))
            else:
                ttl = None
                if "title" in fl.keys():
                    ttl = fl["title"]
                oomm = "song"
                if "_type" in fl.keys() and fl["_type"] == "playlist":
                    oomm = "playlist"
                    ll = []
                    for ell in fl["entries"]:
                        ll.append(LinkHandler(url=ell["url"],options=options))
                    self.playlist += ll
                else:
                    self.playlist += [LinkHandler(url=url,options=options,title=ttl)]
                    
                if not self.hidden and ttl is not None and not "hide" in options:
                    self.send_msg_channel('Adding %s <b>%s</b> to the list' % (oomm,ttl))
                else:
                    self.send_msg_channel('Adding %s <a href="%s">%s</a> to the list' % (oomm,url,url))

                f.close()
                try:
                    os.remove(os.path.expanduser(batchfile))
                except:
                    True
        else:
            self.send_msg_channel('Provided options is not an url')
            self.log.debug('Trying to add %s to the playlist' % url)

        
    def get_all_commands(self):
        return map(lambda x:x[:-3],filter(lambda y:re.search("\.py$",y) is not None and y != "__init__.py",os.listdir(sys.path[0]+"/commands")))
        
    def message_received(self,text):
        message = text.message
        if message[0] == '!':
            message = message[1:].split(' ',1)
            if len(message) > 0:
                command = message[0]
                parameter = ''
                if len(message) > 1:
                    parameter = message[1]
            else:
                return
                
            try:
                getattr(commands,command).execute(self,parameter)
            except:
                if command == "help":
                    self.send_msg_channel("Available commands are " + ", ".join(self.get_all_commands()))
                else:
                    self.send_msg_channel("Incorrect input. Available commands are " + ", ".join(self.get_all_commands()))

            # if command in ["add","loop","stream"] and parameter:
                # options = parameter.split(' ')
                # urlp = options.pop()
                # self.add_to_playlist(get_url(urlp), options = options+[command])
                
            # elif command in ["hadd","hloop","hstream"] and parameter:
                # options = parameter.split(' ')
                # urlp = options.pop()
                # self.add_to_playlist(get_url(urlp), options = options+[command[1:],"hide"])
                
            # elif command == "skip":
                # self.stop()                

            # elif command == 'kill':
                # self.playlist = []
                # self.stop()                        
                # ke = self.downProc.keys()
                # for i in ke:
                    # self.downProc[i].terminate()
                    # self.downProc[i].join()
                    # del self.downProc[i]
                # self.exit = True
                
            # elif command == "clear":
                # self.playlist = []
                # self.stop()
                # ke = self.downProc.keys()
                # for i in ke:
                    # self.downProc[i].terminate()
                    # self.downProc[i].join()
                    # del self.downProc[i]                

            # elif command == 'volume':
                # if parameter is not None and parameter.isdigit() and int(parameter) >= 0 and int(parameter) <= 100:
                    # self.volume = float(float(parameter) / 100)
                    # self.send_msg_channel("Volume has been set to " + str(int(self.volume*100)))
                    # self.set_comment_info()
                # else:
                    # self.send_msg_channel("Current volume is " + str(int(self.volume*100)))

            # elif command == "current":
                # cur = LinkHandler.get_current()
                # if cur is not None:
                    # if not self.hidden and cur.title is not None and "hide" not in cur.options:
                        # self.send_msg_channel('Currently playing <b>%s</b>' % (cur.title))
                    # else:
                        # self.send_msg_channel('Currently playing <a href="%s">%s</a>' % (cur.url,cur.url))
                # else:
                    # self.send_msg_channel("Nothing is currently playing")
                    
            # elif command == "randomize":
                # self.randomize = not self.randomize
                # if self.randomize:
                    # self.send_msg_channel("Randomizer On")
                    # self.log.debug('Randomizer On')
                # else:
                    # self.send_msg_channel("Randomizer Off")
                    # self.log.debug('Randomizer Off')
                    
            # elif command == "hide":
                # self.hidden = not self.hidden
                # if self.hidden:
                    # self.send_msg_channel("Hide mode On")
                    # self.log.debug('Hide mode On')
                # else:
                    # self.send_msg_channel("Hide mode Off")
                    # self.log.debug('Hide mode Off')
                    
            # elif command == "help":
                # self.send_msg_channel("Available commands are !add, !loop, !stream, !hadd, !hloop, !hstream, !skip, !kill, !clear, !volume, !current, !randomize, !hide")
              
            # else:
                # self.send_msg_channel("Incorrect input. Available commands are !add, !loop, !stream, !hadd, !hloop, !hstream, !skip, !kill, !clear, !volume, !current, !randomize, !hide")
        
    def loop(self):
        while not self.exit:
            # Download next song
            if len(self.downProc) < self.n_download:
                todownload = filter(lambda x : not x.downloaded and (x.get_key() not in self.downProc.keys()),self.playlist)
                if todownload != []:
                    tdnext = todownload[0]
                    self.downProc[tdnext.get_key()] = Process(target = tdnext.download, args = ())
                    self.downProc[tdnext.get_key()].start()
                
            # Remove downloads when they are finished
            ke = self.downProc.keys()
            for i in ke:
                if not self.downProc[i].is_alive():
                    for pll in filter(lambda x : x.get_key() == i,self.playlist):
                        pll.downloaded = True
                    del self.downProc[i]
                
            # Manage the current song
            if self.playing:
                while self.mumble.sound_output.get_buffer_size() > 0.5 and self.playing:
                    time.sleep(0.01)
                self.mumble.sound_output.add_sound(audioop.mul(LinkHandler.read(1024), 2, self.volume))
                if LinkHandler.get_current() is None:
                    while self.mumble.sound_output.get_buffer_size() > 0.45:
                        time.sleep(0.01)
                    self.playing = False
            else:
                time.sleep(0.5)
                if self.playlist != []:
                    ind = 0
                    if self.randomize:
                        ind = random.randint(0,len(self.playlist)-1)
                    if self.playlist[ind].play():
                        x = self.playlist.pop(ind)
                        self.playing = True
                        if not self.hidden and x.info is not None and "hide" not in x.options:
                            self.send_msg_channel('Started playing <b>%s</b>' % (x.title))
                        else:
                            self.send_msg_channel(x.show_info())
                self.set_comment_info()
 

        while self.mumble.sound_output.get_buffer_size() > 0:
            time.sleep(0.01)
        time.sleep(0.5)
        
    def stop(self):
        self.playing = False
        time.sleep(0.5)
        LinkHandler.stop()
        self.set_comment_info()
    
    def send_msg_channel(self, msg, channel=None):
        if not channel:
            channel = self.mumble.channels[self.mumble.users.myself['channel_id']]
        channel.send_text_message(msg)
    
        
if __name__ == "__main__":

    log = logging.getLogger(__name__)
    

    p = argparse.ArgumentParser(description='A jukebox for Mumble.')
    
    p.add_argument('ip',metavar='server_ip',help='ip adress of the mumble server the script will try to connect to')
    p.add_argument('--port',type=int,default=64738,help='The server port (default = 64738)')
    p.add_argument('--password', '-p', default='', help="The mumble server's password if required")
    p.add_argument('--name','-n', default='Jukebox', help='The name of the bot')
    p.add_argument('--channel','-c', default='', help='The channel to enter on connection')
    p.add_argument('--log','-l',default='', help='The log file (default = stderr)')
    
    p.add_argument('--verbose','-v',action='store_true',help='Verbose mode')
    p.add_argument('--silent','-s',action='store_true',help='Silent mode')
    p.add_argument('--debug','-d',action='store_true',help='Debug mode')
    p.add_argument('--version', action='version', version='%(prog)s ' + VERSION)

    args = p.parse_args()
    loglvl = logging.WARNING
    if args.verbose:
        loglvl = logging.INFO
    if args.debug:
        loglvl = logging.DEBUG
    if args.silent:
        loglvl = logging.ERROR
    
    log.setLevel(loglvl)
    if args.log != '':
        # ch = logging.StreamHandler(args.log) TO FIX
        ch = logging.StreamHandler()
    else:
        ch = logging.StreamHandler()
    ch.setLevel(loglvl)
    formatter = logging.Formatter('<%(filename)s> [%(levelname)s] %(message)s')
    ch.setFormatter(formatter)
    log.addHandler(ch)
    
    config = ConfigParser.SafeConfigParser()
    try:
        config.read('jukebox.cfg')
    except:
        c = open('jukebox.cfg',w)
        c.write("""
[Init]
port=64738
[Bot]
volume=0.5
download=1
        """)
        c.close()
        config.read('jukebox.cfg')
    
    m = Jukebox(args.ip, password=args.password, port=args.port, channel=args.channel,user=args.name,config=config)
