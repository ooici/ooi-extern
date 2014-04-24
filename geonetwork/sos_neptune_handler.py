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
import json
from bs4 import * 

__author__ = "abird"

class Handler():
	def __init__(self):
		self.PORT = 5454
		self.startup()

	def startup(self):	
		server = WSGIServer(('', self.PORT), self.application).serve_forever()

	def application(self,env, start_response):	        
	        request = env['PATH_INFO']	     
	        
	        if request == '/':
	            start_response('404 Not Found', [('Content-Type', 'application/xml')])
	            return ["<h1>Error<b>please add request information</b>"]
	        elif "service=SOS" not in request:     
	            start_response('404 Not Found', [('Content-Type', 'application/xml')])
	            return ["<h1>Not an sos service request</b>"]
	     	else:
	     		print "query:" + env['QUERY_STRING']		       
		        request = request[1:]
		        print "request:"+request

		        output = ''		        
		        #print "env:"+str(env)
		        neptune_sos_link = "http://dmas.uvic.ca/sos?"+request		        
		        r_text = requests.get(neptune_sos_link)
		        print "---end of request---"

		        #fix the crs code
		        soup = BeautifulSoup(r_text.text)
		        offering_list = soup.findAll("sos:observationoffering")
		        for offering in offering_list:
		        	envelopes = soup.findAll("gml:envelope")    
		        	for e in envelopes:
		        		e['srsName'] = "urn:ogc:def:crs:EPSG:6.5:4326"
		        
		      
		        response_headers = [('Content-Type', 'text/xml; charset=utf-8')]
		        status = '200 OK'
		        #remove the html codes i
		        html_start = "<html><body>"
		        html_end = "</body></html>"
		        xm_response = str(soup)
		        if xm_response.startswith(html_start):
		        	xm_response = xm_response.replace(html_start, "");
		        if xm_response.endswith(html_end):	
		        	xm_response = xm_response.replace(html_end,"");
				
				#add the xml heeader
				xm_response = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"+xm_response
				
	        	start_response(status, response_headers)
        		return [xm_response]
	        