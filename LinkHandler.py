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
    
from Misc import *

sys.path.append(os.path.join(os.path.dirname(__file__), "pymumble"))
import pymumble


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
        if url is not None:
            self.url = url.encode()
        else:
            self.url = None
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
            command_yt = ["youtube-dl", '-w', '-4', '--prefer-ffmpeg','--no-playlist', '-o', filename, '-x', "--audio-format", "opus", '"'+self.url+'"']
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
            command = "youtube-dl -w -4 --prefer-ffmpeg --no-playlist \"%s\" -o - | ffmpeg -i - -ac 1 -f s16le -ar 48000 -" % self.url

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
        command = 'youtube-dl -4 --no-warnings --no-playlist --flat-playlist -J "%s" | jq -r ".title,.thumbnail,.duration" >> %s' % (self.url,infofind)
        sp.call(command, shell = True)

    def get_found_info(self):
        infofind = "~/.musiccache/%s.info" % (hashlib.sha1(self.url).hexdigest())
        f = open(os.path.expanduser(infofind))
        self.title = f.readline()[:-1]
        self.thumbnail = f.readline()[:-1]
        self.duration = f.readline()[:-1]
        f.close()
        if self.title == "null":
            self.title = None
        if self.thumbnail == "null":
            self.thumbnail = None
        if self.duration == "null":
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
                # try:
                htmlimg = formatimage(self.thumbnail)
                # except:
                    # htmlimg = '<img src="%s" width=200 />' % self.url
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
