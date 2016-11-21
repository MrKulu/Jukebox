# -*- coding: utf-8 -*-

import httplib2
import os
import sys
import random
import string
import time
import pickle
import re
import math
import sqlite3
import audioop
import hashlib
import argparse
import logging as log
from codecs import open
from shutil import copyfile
from multiprocessing import Process
import subprocess as sp


sys.path.append(os.path.join(os.path.dirname(__file__), "pymumble"))
import pymumble

VERSION = "0.1a"

class LinkHandler:
    
    __thread = None
    __current = None
    
    def stop():
        if LinkHandler.thread is not None:
            if Linkhandler.__thread.pull() is not None:
                LinkHandler.__thread.terminate()
                log.debug("Stoped playing %s" % LinkHandler.__current.url)
            LinkHandler.__thread = None
            LinkHandler.__current = None

    def get_current():
        if Linkhandler.thread.pull() is None:
            LinkHandler.__current = None
            LinkHandler.__thread = None
        return LinkHandler.__current
    
    
    def __init__(self,url=None,options=[]):
        self.url = url
        self.options = options
        self.started = False
        self.downloaded = False
        
    def download(self):
        if self.downloaded:
            log.warning("Trying to download an already downloaded url ( %s ). Aborting." % self.url)
        else:
            log.debug("Starting download for %s" % self.url)
            
            filename = '~/.musiccache/%s.opus' % (hashlib.sha1(self.url).hexdigest())
            command_yt = ["youtube-dl", '-w', '-4', '--prefer-ffmpeg', '-o', filename, '-x', "--audio-format", "opus", self.url]
            sp.call(command_yt)
            
            self.downloaded = True
            log.debug("Downloading for %s complete" % self.url)
        
    def play(self):
        if (not self.downloaded or self.started):
            if self.started:
                log.warning("Trying to play a previously played song")
            return False
        else:        
            filename = '~/.musiccache/%s.opus' % (hashlib.sha1(self.url).hexdigest())

            command = "ffmpeg -nostdin -i %s -ac 1 -f s16le -ar 48000 -" % filename

            if 'loop' in self.options:
                command = "while true; do \n%s\ndone" % command

            LinkHandler.stop()
            LinkHandler.__current = self
            LinkHandler.__thread = sp.Popen(command, shell=True, stdout=sp.PIPE, bufsize=480)
            self.started = True
            log.debug("Started playing %s" % self.url)
            return True
            
    def get_key(self):
        return self.url



class Jukebox:
    def __init__(self, host, user="Jukebox", port=64738, password="", channel="",jsonread="jsonread.db"):

        self.playing = False
        self.url = None
        self.exit = False
        self.nbexit = 0
        # self.thread = None
        self.volume = 0.5 # Add a config file
        self.n_download = 1 # Add a config file
        self.downProc = {}
        # self.toDownload = []
        # self.toPlay = []
        # self.downloading = False
        # self.param = ''
        self.randomize = False
        # self.predownpurl = None
        self.jsonreadpath = jsonread
        self.playlist = []

        self.mumble = pymumble.Mumble(host, user=user, port=port, password=password, reconnect=True,
                                      debug=False)
        self.mumble.callbacks.set_callback(pymumble.constants.PYMUMBLE_CLBK_TEXTMESSAGERECEIVED, self.message_received)

        self.mumble.start()  # start the mumble thread
        self.mumble.is_ready()  # wait for the connection
        self.mumble.users.myself.unmute()  # make sure the user is not muted
        if channel != "":
            self.mumble.channels.find_by_name(channel).move_in()
        self.mumble.set_bandwidth(200000)
        self.loop()

    def download(self,purl):
        param = ''
        url = purl
        if len(purl.split(' ',1)) > 1:
            param,url = purl.split(' ',1)
            
        log.debug("Started downloading %s (parameter = %s)" % (url, param))
        # self.downloading = True
        filename = '~/.musiccache/%s.opus' % (hashlib.sha1(url).hexdigest())
        command_yt = ["youtube-dl", '-w', '-4', '--prefer-ffmpeg', '-o', filename, '-x', "--audio-format", "opus", url]
        th = sp.Popen(command_yt)
        tmout = time.time()
        while time.time() - tmout < 3600 and th.poll() is None:
            time.sleep(0.1)
        if time.time() - tmout >= 3600:
            self.send_msg_channel("There ha%s been an i%s%sue during download: Procce%s%s didn't terminate after an hour. Aborting")        
        log.debug("Finished downloading %s (parameter = %s)" % (url, param))            
        # self.downloading = False

    def play(self,purl):
        param = ''
        url = purl
        if len(purl.split(' ',1)) > 1:
            param,url = purl.split(' ',1)
            

        if param.lower() == "loop":
            self.toPlay = [purl] + self.toPlay
            self.toDownload = [purl] + self.toDownload
        filename = '~/.musiccache/%s.opus' % (hashlib.sha1(url).hexdigest())
        
        log.debug("Waiting for start of download of %s (parameter = %s)" % (url, param))
        
        if purl not in self.downProc.keys():
            self.toDownload.remove(purl)
            x = purl
            self.downProc[x] = Process(target = self.download, args=(x,))
            self.downProc[x].start()
        
        log.debug("Waiting for %s to finish downloading (parameter = %s)" % (url, param))
        
        self.downProc[purl].join()
        del self.downProc[purl]
        
        log.debug(" Started playing %s (parameter = %s)" % (url, param))
        
        command = "ffmpeg -nostdin -i %s -ac 1 -f s16le -ar 48000 -" % filename
        self.url = url
        
        # time.sleep(0.5)
        self.thread = sp.Popen(command, shell=True, stdout=sp.PIPE, bufsize=480)

        self.param = param
        if self.param.lower() != 'loop':
            self.send_msg_channel('Playing <a href="%s">%s</a>' % (url,url))
        # time.sleep(0.5)

            
    def add_to_playlist(self, url, options=[]):
        if url.startswith("http"):
            c = sqlite3.connect(self.jsonreadpath)
            try:
                listo = c.execute("select * from jsontable") # TODO
            except:
                c.execute("create table jsontable (web text,key text,gu text)")
                listo=[]
            c.commit()
            key = ".webpage_url"
            gu = ""
            for u in listo:
                if u[0] in url:
                    key = u[1]
                    gu = u[2]
            c.close()
            batchfile = "~/.musiccache/%s.batch" % (hashlib.sha1(url).hexdigest())
            try:
                os.remove(os.path.expanduser(batchfile))
            except:
                True
            command = 'youtube-dl -4 --no-warnings --flat-playlist -j %s | jq -r "%s" >> %s' % (url,key,batchfile)
            sp.call(command, shell = True)
            f = open(os.path.expanduser(batchfile))
            l = []
            nl = f.readline().replace('\n','')
            while nl != '':
                l += [LinkHandler(url=gu+nl,options = options)]
                nl = f.readline().replace('\n','')
            if len(l) == 1:
                l = [LinkHandler(url=url,options = options)]
                self.send_msg_channel('Adding song <a href="%s">%s</a> to the list' % (url,url))
            else:
                self.send_msg_channel('Adding playlist <a href="%s">%s</a> to the list' % (url,url))
            self.playlist += l
            f.close()
        else:
            self.send_msg_channel('Provided options is not an url')
            log.debug('Trying to add %s to the playlist' % url)

        
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

            if command == "add" and parameter:
                options=[]
                if len(parameter.split(' ',1)) > 1 and not get_url(parameter):
                    options = parameter.split(' ',1)
                    urlp = options.pop()
                self.add_to_playlist(get_url(urlp), options = options)
                
            elif command == "loop":
                self.add_to_playlist(get_url(parameter), options=["loop"])

            elif command == "skip":
                self.stop()                

            elif command == 'kill':
                self.playlist = []
                self.stop()
                ke = self.downProc.keys()
                for i in ke:
                    self.downProc[i].join()
                    del self.downProc[i]
                self.exit = True
                
            elif command == "clear":
                self.playlist = []
                self.stop()
                ke = self.downProc.keys()
                for i in ke:
                    self.downProc[i].join()
                    del self.downProc[i]
               

            elif command == 'volume':
                if parameter is not None and parameter.isdigit() and int(parameter) >= 0 and int(parameter) <= 100:
                    self.volume = float(float(parameter) / 100)
                    self.send_msg_channel("Volume has been set to " + str(int(self.volume*100)))
                else:
                    self.send_msg_channel("Current volume is " + str(int(self.volume*100)))
                    
            elif command == 'jsonkey':
                self.update_jsonread(*(parameter.split(' ',2)))

            elif command == "current":
                cur = LinkHandler.get_current()
                if cur is not None:
                    self.send_msg_channel('Currently playing <a href="%s">%s</a>' % (cur.url,cur.url))
                else:
                    self.send_msg_channel("Nothing is currently playing")
                    
            elif command == "randomize":
                self.randomize = not self.randomize
                if self.randomize:
                    self.send_msg_channel("Randomizer On")
                    log.debug('Randomizer On')
                else:
                    self.send_msg_channel("Randomizer Off")
                    log.debug('Randomizer Off')
                    
            elif command == "help":
                self.send_msg_channel("Available commands are !add, !loop, !skip, !kill, !clear, !volume, !jsonkey, !current, !randomize")
              
            else:
                self.send_msg_channel("Incorrect input. Available commands are !add, !loop, !skip, !kill, !clear, !volume, !jsonkey, !current, !randomize")
        
    def loop(self):
        while not self.exit:
            # Download next song
            todownload = filter(lambda x : not x.downloaded,self.playlist)
            if todownload != [] and len(self.downProc) < self.n_download:
                tdnext = todownload[0]
                self.downProc[tdnext.get_key()] = Process(target = tdnext.download, args = ())
                self.downProc[tdnext.get_key()].start()
                
            # Remove downloads when they are finished
            for i in self.downProc:
                if not self.downProc[i].is_alive():
                    del self.downProc[i]
                
            # Manage the current song
            if self.playing:
                while self.mumble.sound_output.get_buffer_size() > 0.5 and self.playing:
                    time.sleep(0.01)
                self.mumble.sound_output.add_sound(audioop.mul(self.thread.stdout.read(1024), 2, self.volume))
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
                        self.playlist.pop(ind)
                        self.playing = True
 

        while self.mumble.sound_output.get_buffer_size() > 0:
            time.sleep(0.01)
        time.sleep(0.5)
        
    def stop(self):
        if self.thread:
            self.playing = False
            time.sleep(0.5)
            LinkHandler.stop()
    
    def send_msg_channel(self, msg, channel=None):
        if not channel:
            channel = self.mumble.channels[self.mumble.users.myself['channel_id']]
        channel.send_text_message(msg)

    def update_jsonread(self,website,jsonkey=".webpage_url",geturl=""): # TODO :(
        if re.match("^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$",website) is None:
            self.send_msg_channel("The website name is not valid")
        elif re.match("[\/\w \.-]*",jsonkey) is None:
            self.send_msg_channel("The jsonkey is not valid")
        else:
            if get_url(geturl):
                geturl = get_url(geturl)
            c = sqlite3.connect(self.jsonreadpath)
            b = False
            key = None
            gu = None
            try:
                listo = c.execute("select * from jsontable where web=?",(website,))
                for u in listo:
                    b = True
                    key = u[1]
                    gu = u[2]
                c.execute("delete from jsontable where web=?",(website,))
            except:
                c.execute("create table jsontable (web text,key text,gu text)")
            c.commit()
            c.execute("insert into jsontable values (?,?,?)",(website,jsonkey,geturl,))
            if b:
                self.send_msg_channel("Updated %s for %s" % (self.jsonreadpath,website))
            else:
                self.send_msg_channel("Adding %s to %s" % (website,self.jsonreadpath))
            c.commit()
            c.close()
    
def get_url(url):
    if url.startswith('http'):
        return url
    p = re.compile('href="(.+)"', re.IGNORECASE)
    res = re.search(p, url)
    if res:
        return res.group(1)
    else:
        return None
        
if __name__ == "__main__":

    p = argparse.ArgumentParser(description='A jukebox for Mumble.')
    
    p.add_argument('ip',metavar='server_ip',help='ip adress of the mumble server the script will try to connect to')
    
    p.add_argument('--port',type=int,default=64738,help='The server port (default = 64738)')
    
    p.add_argument('--password', '-p', default='', help='The mumble server password if required')
    
    p.add_argument('--name','-n', default='Jukebox', help='The name of the bot')
    
    p.add_argument('--channel','-c', default='', help='The channel to enter on connection')
    
    p.add_argument('--jsonread',default="jsonread.db", help='The path to the jsonread file')
    
    p.add_argument('--verbose','-v',action='store_true',help='Verbose mode')
    p.add_argument('--silent','-s',action='store_true',help='Silent mode')
    p.add_argument('--debug','-d',action='store_true',help='Debug mode')
    
    p.add_argument('--version', action='version', version='%(prog)s ' + VERSION)

    args = p.parse_args()
    loglvl = log.WARNING
    if args.verbose:
        loglvl = log.INFO
    if args.debug:
        loglvl = log.DEBUG
    if args.silent:
        loglvl = log.ERROR
    
    log.basicConfig(format="<%(filename)s> [%(levelname)s] %(message)s",level=loglvl)
    
    m = Jukebox(args.ip, password=args.password, port=args.port, channel=args.channel,user=args.name)
