#!/usr/bin/python
"""
handler for sos responses from neptune
"""
import httplib2
import json
import requests
import ast
import yaml
import logging
from gevent.pywsgi import WSGIServer
import requests
__author__ = "abird"

class Handler():
	def __init__(self):
		self.PORT = 5454
		self.startup()

	def startup(self):	
		server = WSGIServer(('', self.PORT), self.application).serve_forever()

	def application(self,env, start_response):
	        request = env['PATH_INFO']
	        print "query:" + env['QUERY_STRING']
	        request = request[1:]
	        output = ''
	        print "request"+request
	        print "env:"+env

	        if request == '/':
	            start_response('404 Not Found', [('Content-Type', 'text/html')])
	            return ["<h1>Error<b>please add request information</b>"]

	     	else:
	        	start_response('200 OK', [('Content-Type', 'text/html')])
        		return ['<b>' + request + '<br>'+ output +'</b>']
	        