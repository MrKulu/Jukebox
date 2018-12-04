# -*- coding: utf-8 -*-

from commands import *
import commands
from __builtin__ import *

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
import datetime
try:
    import ImageFile
    import Image
except ImportError:
    from PIL import ImageFile
    from PIL import Image

from LinkHandler import *

from Misc import *

sys.path.append(os.path.join(os.path.dirname(__file__), "pymumble"))
import pymumble

VERSION = "0.4a04_12_2018"
CONF_DFLT = {
    "volume":0.5,
    "download":1
}
FORMAT = "<%(filename)s> [%(levelname)s] %(message)s"
BONSOIR = "../bonsoir.aac"
WEDNESDAY = "../wednesday.opus"

class Jukebox:
    def __init__(self, host, user="Jukebox", port=64738, password="", channel="", config=None):

        self.playing = False
        self.url = None
        self.exit = False
        self.nbexit = 0

        self.volume = config.get("Bot","volume")
        self.n_download = config.get("Bot","download")
        self.downProc = {}
        self.randomize = False
        self.hidden = False
        self.playlist = []
        
        self.log = logging.getLogger(__name__)

        self.mumble = pymumble.Mumble(host, user=user, port=port, password=password, reconnect=True,
                                      debug=False)
        self.mumble.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.message_received)
        self.mumble.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_USERCREATED, self.user_created)
        self.mumble.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_USERUPDATED, self.user_updated)
                
        
        self.mumble.start()  # start the mumble thread
        self.mumble.is_ready()  # wait for the connection
        self.mumble.users.myself.unmute()  # make sure the user is not muted
        self.set_comment_info()
        if channel != "":
            self.mumble.channels.find_by_name(channel).move_in()
        self.mumble.set_bandwidth(200000)
        self.log.warning("test-w")
        self.log.error("test-e")
        self.log.debug("test-d")
        self.log.info("test-i")
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
            command = 'youtube-dl -4 --no-warnings --no-playlist --flat-playlist --dump-single-json "%s" >> %s' % (url,batchfile)
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
        return sorted(map(lambda x:x[:-3],filter(lambda y:re.search("\.py$",y) is not None and y != "__init__.py",os.listdir(sys.path[0]+"/commands"))))

    def user_created(self,user):
        me = self.mumble.users.myself
        if me is not None and user is not None and "channel_id" in me and "channel_id" in user and user["channel_id"] == me["channel_id"]:
            self.play_bonsoir(BONSOIR)

    def user_updated(self,user,actions):
        me = self.mumble.users.myself
        if me is not None and user is not None and "channel_id" in user and "channel_id" in me and "channel_id" in actions and user["channel_id"] == me["channel_id"]:
            self.play_bonsoir(BONSOIR)
                        

    def play_bonsoir(self,filen):
        oofi = filen
        if datetime.datetime.now().strftime("%A") == "Wednesday":
            oofi = WEDNESDAY
        command = "ffmpeg -nostdin -i %s -ac 1 -f s16le -ar 48000 -" % oofi
        bonsoir = sp.Popen(command, shell=True, stdout=sp.PIPE, bufsize=-1)
        (bsound,_) = bonsoir.communicate()
        self.mumble.sound_output.add_sound(audioop.mul(bsound,2,self.volume))
        
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
            except AttributeError:
                if command == "help":
                    self.send_msg_channel("Available commands are " + ", ".join(self.get_all_commands()))
                else:
                    self.send_msg_channel("Incorrect input. Available commands are " + ", ".join(self.get_all_commands()))
        
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
                    self.mumble.sound_output.add_sound(audioop.mul(LinkHandler.read(1024),2,self.volume))
                    while self.mumble.sound_output.get_buffer_size() > 0.5:
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
            time.sleep(0.5)
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

    if args.log != '':
        logging.basicConfig(filename=args.log,level=loglvl,format=FORMAT)
    else:
        logging.basicConfig(level=loglvl,format=FORMAT)
        
    config = ConfigParser.SafeConfigParser(CONF_DFLT)
    config.read('jukebox.cfg')
    
    m = Jukebox(args.ip, password=args.password, port=args.port, channel=args.channel,user=args.name,config=config)
