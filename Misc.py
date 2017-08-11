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

    if ret_image_info.size is not None and ret_image_info.size/1024 < 256:
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
    
    