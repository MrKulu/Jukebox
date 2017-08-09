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


sys.path.append(os.path.join(os.path.dirname(__file__), "pymumble"))
import pymumble

VERSION = "0.3b5"

class LinkHandler:
    
    __thread = None
    __current = None
    
    @classmethod
    def stop(cls):
        if cls.__thread is not None:
            if cls.__thread.poll() is None:
                cls.__thread.terminate()
                if cls.__current is not None:
                    cls.__current.log.debug("Stoped playing %s" % cls.__current.url)
            cls.__thread = None
            cls.__current = None

    @classmethod
    def get_current(cls):
        if cls.__thread is None or cls.__thread.poll() is not None:
            cls.__current = None
            cls.__thread = None
        return cls.__current
        
    @classmethod
    def read(cls,n):
        if cls.__thread is not None:
            return cls.__thread.stdout.read(n)
        else:
            cls.__current = None
            return ""
    
    def __init__(self,url=None,options=[],title=None):
        self.url = url
        self.options = options
        self.started = False
        self.downloaded = False
        self.log = logging.getLogger(__name__)
        self.title = title
        self.thumbnail = None
        self.duration = None
        self.info = None
        
    def download(self):
        if self.info is None:
            self.find_info()
        if self.downloaded:
            self.log.warning("Trying to download an already downloaded url ( %s ). Aborting." % self.url)
        elif 'stream' in self.options:
            True
        else:
            self.log.debug("Starting download for %s" % self.url)
            
            filename = '~/.musiccache/%s.opus' % (hashlib.sha1(self.url).hexdigest())
            command_yt = ["youtube-dl", '-w', '-4', '--prefer-ffmpeg','--no-playlist', '-o', filename, '-x', "--audio-format", "opus", self.url]
            sp.call(command_yt)
            
            self.log.debug("Downloading for %s complete" % self.url)
        
    def play(self):
        if (not self.downloaded or self.started):
            if self.started:
                self.log.warning("Trying to play a previously played song")
            return False
        elif 'stream' in self.options:
            if self.info is None:
                self.get_found_info()
            self.stream()
            return True
        else:
            if self.info is None:
                self.get_found_info()
            filename = '~/.musiccache/%s.opus' % (hashlib.sha1(self.url).hexdigest())

            command = "ffmpeg -nostdin -i %s -ac 1 -f s16le -ar 48000 -" % filename

            if 'loop' in self.options:
                command = "while true; do %s ; done" % command

            LinkHandler.stop()
            LinkHandler.__current = self
            LinkHandler.__thread = sp.Popen(command, shell=True, stdout=sp.PIPE, bufsize=480)
            self.started = True
            self.log.debug("Started playing %s" % self.url)
            return True
            
    def stream(self):
        if self.started:
            self.log.warning("Trying to stream an already played song")
            return False
        else:
            
            filename = '~/.musiccache/%s.opus' % (hashlib.sha1(self.url).hexdigest())
            try:
                os.remove(os.path.expanduser(filename))
            except:
                True            
            command = "youtube-dl -w -4 --prefer-ffmpeg --no-playlist %s -o - | ffmpeg -i - -ac 1 -f s16le -ar 48000 -" % self.url

            #if 'loop' in self.options:
            #    command = "youtube-dl -w -4 --prefer-ffmpeg --no-playlist %s -o - | ffmpeg -i - -c opus -ac 1 -f s16le -ar 48000 -f tee -map 0:a \"%s|pipe:\";while true; do ffmpeg -nostdin -i %s -ac 1 -f s16le -ar 48000 - ; done" % (self.url,os.path.expanduser(filename),filename)
            # TO FIX

            
            LinkHandler.stop()
            LinkHandler.__current = self
            LinkHandler.__thread = sp.Popen(command, shell=True, stdout=sp.PIPE, bufsize=480)
            self.started = True
            self.log.debug("Started streaming %s" % self.url)
            return True
            
    def get_key(self):
        return self.url

    def find_info(self):
        self.info = True
        infofind = "~/.musiccache/%s.info" % (hashlib.sha1(self.url).hexdigest())
        try:
            os.remove(os.path.expanduser(infofind))
        except:
            True
        command = 'youtube-dl -4 --no-warnings --no-playlist --flat-playlist -J %s | jq -r ".title,.thumbnail,.duration" >> %s' % (self.url,infofind)
        sp.call(command, shell = True)

    def get_found_info(self):
        infofind = "~/.musiccache/%s.info" % (hashlib.sha1(self.url).hexdigest())
        f = open(os.path.expanduser(infofind))
        self.title = f.readline()[:-1]
        self.thumbnail = f.readline()[:-1]
        self.duration = f.readline()[:-1]
        f.close()
        if self.title == "none":
            self.title = None
        if self.thumbnail == "none":
            self.thumbnail = None
        if self.duration == "none":
            self.duration = None
        else:
            self.duration = int_to_time(int(float(self.duration)))
        try:
            os.remove(os.path.expanduser(infofind))
        except:
            True
            
    def show_info(self):
        dur = ""
        if self.duration != None:
            dur += " (" + self.duration + ")"
        if self.title == None:
            return ('Started playing <a href="%s">%s</a>' % (self.url,self.url)) + dur
        else:
            if self.thumbnail == None:
                return ('Started playing <b><a href="%s">%s</a></b>' % (self.url,self.title)) + dur
            else:
                try:
                    htmlimg = formatimage(self.thumbnail)
                else:
                    htmlimg = '<img src="%s" width=200 />' % self.url
                return ("""<table>
                <tr>
					<td align="center"><i>Now playing...</i></td>
				</tr>
			 	<tr>
					<td align="center"><a href="%s">%s<a></td>
				</tr>
				<tr>
					<td align="center"><b><a href="%s">%s</a>%s</b></td>
				</tr>
                </table>""" % (self.url,htmlimg,self.url,self.title,dur))


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

            if command in ["add","loop","stream"] and parameter:
                options = parameter.split(' ')
                urlp = options.pop()
                self.add_to_playlist(get_url(urlp), options = options+[command])
                
            elif command in ["hadd","hloop","hstream"] and parameter:
                options = parameter.split(' ')
                urlp = options.pop()
                self.add_to_playlist(get_url(urlp), options = options+[command[1:],"hide"])
                
            elif command == "skip":
                self.stop()                

            elif command == 'kill':
                self.playlist = []
                self.stop()                        
                ke = self.downProc.keys()
                for i in ke:
                    self.downProc[i].terminate()
                    self.downProc[i].join()
                    del self.downProc[i]
                self.exit = True
                
            elif command == "clear":
                self.playlist = []
                self.stop()
                ke = self.downProc.keys()
                for i in ke:
                    self.downProc[i].terminate()
                    self.downProc[i].join()
                    del self.downProc[i]                

            elif command == 'volume':
                if parameter is not None and parameter.isdigit() and int(parameter) >= 0 and int(parameter) <= 100:
                    self.volume = float(float(parameter) / 100)
                    self.send_msg_channel("Volume has been set to " + str(int(self.volume*100)))
                    self.set_comment_info()
                else:
                    self.send_msg_channel("Current volume is " + str(int(self.volume*100)))

            elif command == "current":
                cur = LinkHandler.get_current()
                if cur is not None:
                    if not self.hidden and cur.title is not None and "hide" not in cur.options:
                        self.send_msg_channel('Currently playing <b>%s</b>' % (cur.title))
                    else:
                        self.send_msg_channel('Currently playing <a href="%s">%s</a>' % (cur.url,cur.url))
                else:
                    self.send_msg_channel("Nothing is currently playing")
                    
            elif command == "randomize":
                self.randomize = not self.randomize
                if self.randomize:
                    self.send_msg_channel("Randomizer On")
                    self.log.debug('Randomizer On')
                else:
                    self.send_msg_channel("Randomizer Off")
                    self.log.debug('Randomizer Off')
                    
            elif command == "hide":
                self.hidden = not self.hidden
                if self.hidden:
                    self.send_msg_channel("Hide mode On")
                    self.log.debug('Hide mode On')
                else:
                    self.send_msg_channel("Hide mode Off")
                    self.log.debug('Hide mode Off')
                    
            elif command == "help":
                self.send_msg_channel("Available commands are !add, !loop, !stream, !hadd, !hloop, !hstream, !skip, !kill, !clear, !volume, !current, !randomize, !hide")
              
            else:
                self.send_msg_channel("Incorrect input. Available commands are !add, !loop, !stream, !hadd, !hloop, !hstream, !skip, !kill, !clear, !volume, !current, !randomize, !hide")
        
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
    
def get_url(url):
    if url.startswith('http'):
        return url
    p = re.compile('href="(.+)"', re.IGNORECASE)
    res = re.search(p, url)
    if res:
        return res.group(1)
    else:
        return None
        
def int_to_time(n):
    m = n/60
    if m > 60:
        return "%d:%02d:%02d" % (m/60,m%60,n%60)
    else:
        return "%02d:%02d" % (m,n%60)
        
def formatimage(url):
    """Funtion resizes thumbnails to fit in the Mumble client.
    code copied and modified from https://github.com/aselus-hub/chatimg-mumo 
    """
    
    class ImageInfo(object):
        """Class for storing image information.
            size = size of the image in bytes
            width = width of the image in pixels
            height = height of the image in pixels
        """
        def __init__(self,
                     size=None,
                     width=None,
                     height=None):
            self.size = size
            self.width = width
            self.height = height
            
            
    open_url = urllib2.urlopen(url)

    ret_image_info = None
    if "image" in open_url.headers.get("content-type"):
        ret_image_info = ImageInfo()

        ret_image_info.size = open_url.headers.get("content-length") or None
        if ret_image_info.size:
            ret_image_info.size = int(ret_image_info.size)
            
        img_parser = ImageFile.Parser()
        for block_buf in readImageDataPerByte(urllib2.urlopen(open_url.geturl())):
            img_parser.feed(block_buf)
            if img_parser.image:
                ret_image_info.width, ret_image_info.height = img_parser.image.size

    injected_img = None

    if ret_image_info.size/1024 < 256:
        encoded = base64.b64encode(open_url.read())
        injected_img = ('<img src="data:image/jpeg;charset=utf-8;base64,' +
                        str(encoded) +
                        '" %s />' % getModifiers(ret_image_info))
    else:
        image = Image.open(StringIO.StringIO(open_url.read()))
        image.thumbnail((200, 200), Image.ANTIALIAS)
        trans = StringIO.StringIO()
        image.save(trans, format="JPEG")
        encoded = base64.b64encode(trans.getvalue())
        injected_img = ('<img src="data:image/jpeg;charset=utf-8;base64,' +
                        str(encoded) +
                        '"  />')

    return injected_img
    
def readImageDataPerByte(open_url):
    """Utility method for reading a an image, reads 1kb at a time.
    :param open_url:  urlinfo opened urllib2 object for the image url.
    :return: 1024 byte data set
    """
    data = open_url.read(1024)
    while data:
        yield data
        data = open_url.read(1024)
        
def getModifiers(img_info):
    """ If the image is greater then the limits for images set in config, generates an html style descriptor.
    :param img_info: ImageInfo - the full img_info for this image.
    :return: str containing the modifier needed in order to resize the image in html, or blank if no resizing
    is required.
    """
    modifiers = ""
    width_percent_reduction = 0
    height_percent_reduction = 0
    max_width = float(200)
    max_height = float(200)
    if max_width and img_info.width > max_width:
        width_percent_reduction = (img_info.width / max_width) - 1.0
    if max_height and img_info > max_height:
        height_percent_reduction = (img_info.height / max_height) - 1.0

    if width_percent_reduction > 0 and width_percent_reduction > height_percent_reduction:
        modifiers = " width=\"%s\" " % max_width
    elif height_percent_reduction > 0:
        modifiers = " height=\"%d\" " % max_height

    return modifiers
    
    
        
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
