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

VERSION = "1.0a1"


class LinkHandler:
    def __init__(self,url=None,options=[],sender=None):
        self.url = url
        self.options = options
        self.sender = sender
        
        self.downloaded = False
        
    def download(self):
        return True # TODO. not thread
        
    def play(self):
        return True # TODO. not thread
    
    

class Jukebox:
    def __init__(self, host, user="Jukebox", port=64738, password="", channel="",jsonread="jsonread.db"):


        self.playing = False
        self.url = None
        self.exit = False
        self.nbexit = 0
        self.thread = None
        self.volume = 0.5
        self.downProc = {}
        self.toDownload = []
        self.toPlay = []
        self.downloading = False
        self.param = ''
        self.randomize = False
        self.predownpurl = None
        self.jsonreadpath = jsonread

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
            
        print "[debug] Started downloading %s (parameter = %s)" % (url, param)
        # self.downloading = True
        filename = '~/.musiccache/%s.opus' % (hashlib.sha1(url).hexdigest())
        command_yt = ["youtube-dl", '-w', '-4', '--prefer-ffmpeg', '-o', filename, '-x', "--audio-format", "opus", url]
        th = sp.Popen(command_yt)
        tmout = time.time()
        while time.time() - tmout < 3600 and th.poll() is None:
            time.sleep(0.1)
        if time.time() - tmout >= 3600:
            self.send_msg_channel("There ha%s been an i%s%sue during download: Procce%s%s didn't terminate after an hour. Aborting")        
        print "[debug] Finished downloading %s (parameter = %s)" % (url, param)            
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
        
        print "[debug] Waiting for start of download of %s (parameter = %s)" % (url, param)
        
        
        
        if purl not in self.downProc.keys():
            self.toDownload.remove(purl)
            x = purl
            self.downProc[x] = Process(target = self.download, args=(x,))
            self.downProc[x].start()
        
        print "[debug] Waiting for %s to finish downloading (parameter = %s)" % (url, param)
        
        self.downProc[purl].join()
        del self.downProc[purl]
        
        print "[debug] Started playing %s (parameter = %s)" % (url, param)
        
        command = "ffmpeg -nostdin -i %s -ac 1 -f s16le -ar 48000 -" % filename
        self.url = url
        
        # time.sleep(0.5)
        self.thread = sp.Popen(command, shell=True, stdout=sp.PIPE, bufsize=480)

        self.param = param
        if self.param.lower() != 'loop':
            self.send_msg_channel('Playing <a href="%s">%s</a>' % (url,url))
        # time.sleep(0.5)

            
        # self.playing = True


            
    def add_to_playlist(self, url):
        param=''
        if len(url.split(' ',1)) > 1:
            param,url = url.split(' ',1)
            param += ' '
        c = sqlite3.connect(self.jsonreadpath)
        try:
            listo = c.execute("select * from jsontable")
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
        command = "youtube-dl -4 --no-warnings --flat-playlist -j " + url + ' | jq -r "%s" >> %s' % (key,batchfile)
        thbatch = sp.Popen(command, shell = True)
        thbatch.wait()
        f = open(os.path.expanduser(batchfile))
        l = []
        nl = f.readline().replace('\n','')
        while nl != '':
            l += [param+gu+nl]
            nl = f.readline().replace('\n','')
        if len(l) == 1:
            l = [param + url]
            self.send_msg_channel('Adding song <a href="%s">%s</a> to the list' % (url,url))
        else:
            self.send_msg_channel('Adding playlist <a href="%s">%s</a> to the list' % (url,url))
        self.toDownload += l
        self.toPlay += l
        f.close()
        #self.downProc[url] = Process(target = self.download, args=(url,))
        #self.downProc[url].start()
        #self.play(url)
        
        
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
                param=''
                if len(parameter.split(' ',1)) > 1 and not get_url(parameter):
                    param,parameter = parameter.split(' ',1)
                    param += ' '
                self.add_to_playlist(param.lower() + get_url(parameter))
                
            elif command == "loop":
                self.add_to_playlist("loop " + get_url(parameter))

            elif command == "skip":
                if self.param.split(' ')[0].lower() == "loop":
                    self.toPlay = self.toPlay[1:]
                    self.toDownload = self.toDownload[1:]
                self.stop()
                

            elif command == 'kill':
                self.toPlay = []
                self.toDownload = []
                self.stop()
                ke = self.downProc.keys()
                for i in ke:
                    self.downProc[i].join()
                    del self.downProc[i]
                self.downloading = False
                self.exit = True
                
            elif command == "clear":
                self.toPlay = []
                self.toDownload = []
                self.stop()
                ke = self.downProc.keys()
                for i in ke:
                    self.downProc[i].join()
                    del self.downProc[i]
                self.downloading = False
               

            elif command == 'volume':
                if parameter is not None and parameter.isdigit() and int(parameter) >= 0 and int(parameter) <= 100:
                    self.volume = float(float(parameter) / 100)
                    self.send_msg_channel("Volume has been set to " + str(int(self.volume*100)))
                else:
                    self.send_msg_channel("Current volume is " + str(int(self.volume*100)))
                    
            elif command == 'jsonkey':
                self.update_jsonread(*(parameter.split(' ',2)))

            elif command == "current":
                if self.url is not None:
                    self.send_msg_channel('Currently playing <a href="%s">%s</a>' % (self.url,self.url))
                else:
                    self.send_msg_channel("Nothing is currently playing")
                    
            elif command == "randomize":
                self.randomize = not self.randomize
                if self.randomize:
                    self.send_msg_channel("Randomizer On")
                else:
                    self.send_msg_channel("Randomizer Off")
                    
            elif command == "help":
                self.send_msg_channel("Available commands are !add, !loop, !skip, !kill, !clear, !volume, !jsonkey, !current, !randomize")
              
            else:
                self.send_msg_channel("Incorrect input. Available commands are !add, !loop, !skip, !kill, !clear, !volume, !jsonkey, !current, !randomize")
        
    def loop(self):
        while not self.exit:
            if self.toDownload != [] and not self.downloading:
                x = self.toDownload.pop(0)
                self.downProc[x] = Process(target = self.download, args=(x,))
                self.downProc[x].start()
                self.downloading = True
                self.predownpurl = x
            elif self.downloading and not self.downProc[self.predownpurl].is_alive():
                self.downloading = False
                self.predownpurl = None
                
            if self.playing:
                while self.mumble.sound_output.get_buffer_size() > 0.5 and self.playing:
                    time.sleep(0.01)
                self.mumble.sound_output.add_sound(audioop.mul(self.thread.stdout.read(1024), 2, self.volume))
                if self.thread.poll() is not None:
                    while self.mumble.sound_output.get_buffer_size() > 0.45:
                        time.sleep(0.01)
                    self.thread = None
                    self.playing = False
            else:
                time.sleep(0.5)
                if self.toPlay != []:
                    if self.randomize and self.param != "loop":
                        x = self.toPlay.pop(random.randint(0,len(self.toPlay)-1))
                    else:
                        x = self.toPlay.pop(0)
                    self.playing = True
                    self.play(x)
 

        while self.mumble.sound_output.get_buffer_size() > 0:
            time.sleep(0.01)
        time.sleep(0.5)
        
    def stop(self):
        if self.thread:
            self.playing = False
            time.sleep(0.5)
            self.thread.kill()
            self.thread = None
            self.url = None
            self.param = ''
    
    def send_msg_channel(self, msg, channel=None):
        if not channel:
            channel = self.mumble.channels[self.mumble.users.myself['channel_id']]
        channel.send_text_message(msg)

    def update_jsonread(self,website,jsonkey=".webpage_url",geturl=""):
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
        return False
        
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
    
    m = Jukebox(args.ip, password=args.password, port=args.port, channel=args.channel)
