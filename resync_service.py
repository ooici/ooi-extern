#!/usr/bin/python
"""
WSGI geonetwork metadata resync service
"""
from gevent.pywsgi import WSGIServer
import httplib2
import json
import requests
from bs4 import *
import ast
import yaml
import logging

import time

__author__ = "abird"

#see the folling for reference
#http://geonetwork-opensource.org/manuals/trunk/eng/developer/xml_services/metadata_xml_search_retrieve.html#search-metadata-xml-search

#headers
headers = {'content-type': 'application/xml'}
req_harvesters = "requestedharvesters"

class DataProductImporter():
	def __init__(self):
		logger = logging.getLogger('resync_service')
		hdlr = logging.FileHandler('resync_service.log')
		formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
		hdlr.setFormatter(formatter)
		logger.addHandler(hdlr)
		logger.setLevel(logging.DEBUG)

		self.logger = logger
		self.logger.info("Setting up geonetwork to RR resync service...")
		self.startup()
	def startup(self):	
		stream = open("extern.yml", 'r')
		ion_config = yaml.load(stream)
		self.logger.info("opened yml file")

		self.RR_PORT = 8848

		self.logger.info('Serving on '+str(self.RR_PORT)+'...')
		server = WSGIServer(('', self.RR_PORT), self.application).serve_forever()

	def application(self, env, start_response):	
		request = env['PATH_INFO']
		request = request[1:]
		output = ''
		if request == '/':
			start_response('404 Not Found', [('Content-Type', 'text/html')])
			return ["<h1>Error<b>please add request information</b>"]
		else:
			req = request.split("&")
			param_dict = {}
			if len(req) > 1:
				for param in req:
					params = param.split("=")
 					param_dict[params[0]] = params[1]

				if param_dict.has_key(req_harvesters) and param_dict.has_key("ooi"):
					site_dict = self.get_harvester_list()
					self.get_all_available_meta_data_records(site_dict)		

					start_response('200 ok', [('Content-Type', 'text/html')])
					return ['<b>ALIVE<BR>' + request + '</b>']
				else:
					start_response('400 Bad Request', [('Content-Type', 'text/html')])
					return ['<b>ERROR IN PARAMS<BR>' + request + '<br>' + output + '</b>']					
			else:
				start_response('400 Bad Request', [('Content-Type', 'text/html')])
				return ['<b>ERROR NO PARAMS<BR>' + request + '<br>' + output + '</b>']
					

	def get_harvester_list(self):
		'''
		creates a dict of the harvester names and id's that are valid 
		'''
		r = requests.get('http://eoi-dev1.oceanobservatories.org:8080/geonetwork/srv/eng/harvesting/xml.harvesting.get',auth=("admin","admin"),headers=headers)
		r.status_code
		soup = BeautifulSoup(r.text)
		sites = soup.find_all("site")
		site_dict = dict()

		accept_list = ["neptune","ioos","ioos2"]

		for site in sites:    
		    name = site.find("name").text
		    if name in accept_list:
		        uuid = site.find("uuid").text
		        site_dict[uuid] = name
		return site_dict

	def get_all_available_meta_data_records(self,site_dict):		
		'''
		get all resources
		'''
		r = requests.get('http://eoi-dev1.oceanobservatories.org:8080/geonetwork/srv/eng/xml.search',auth=("admin","admin"),headers=headers)
		r.status_code
		soup = BeautifulSoup(r.text)
		meta_data_records = soup.find_all("geonet:info")

		#loop through the records and get the meta data
		count = 0
		t0 = time.time()
		for record in meta_data_records:
			try:
				rec_source = record.find("source").text		        
				#is the source in the list
				if rec_source in site_dict.keys():
					#which harvester did it come from?
					from_name = site_dict[rec_source]
					count +=1
					rec_id = record.find("id").text
					get_meta_data_record(rec_id)
					rec_uuid = record.find("uuid").text
					rec_schema = record.find("schema").text
					rec_create = record.find("createDate").text
					rec_change = record.find("changeDate").text
					rec_cat = record.find("category").text

			except Exception:
				#just pass on to the next one if we encounter an error
				 pass
		t1 = time.time()
		print "Total number:",len(meta_data_records)
		print "Count of valid ones:",count
		print "Total time:", t1-t0

	def get_meta_data_record(self,uuid):
		'''
		get the meta data for a given uuid meta data resource
		'''
		payload = '''<?xml version="1.0" encoding="UTF-8"?>
            <request>
            	<uuid>%s</uuid>
            </request>''' % (uuid)

		r = requests.post('http://eoi-dev1.oceanobservatories.org:8080/geonetwork/srv/eng/xml.metadata.get',data=payload,auth=("admin","admin"),headers=headers)
		r.status_code
		soup = BeautifulSoup(r.text)
