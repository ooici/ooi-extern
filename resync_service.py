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
import psycopg2
import time
import simplejson as json
import numpy as np

__author__ = "abird"

#see the folling for reference
#http://geonetwork-opensource.org/manuals/trunk/eng/developer/xml_services/metadata_xml_search_retrieve.html#search-metadata-xml-search

#headers
headers = {'content-type': 'application/xml'}
sync_harvesters = "syncharvesters"


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

		##TODO add to yml file
		self.GEONETWORK_SERVER = "http://r3-pg-test02.oceanobservatories.org:8080"
		self.GEONETWORK_DB_SERVER = "r3-pg-test02.oceanobservatories.org"
		self.GEONETWORK_DB = "geonetwork"
		self.RR_PORT = 8848
		self.GEONETWORK_USER = 'ooici'
		self.GEONETWORK_PASS= 'ooici'

		self.SGS_URL = self.url = 'http://%s:%s/ion-service/' % ('localhost', 5000)


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

				if param_dict.has_key(sync_harvesters) and param_dict.has_key("ooi"):
					try:
						print "requested sync harvesters:",param_dict[sync_harvesters]
						site_dict = self.get_harvester_list()
						#self.get_all_available_meta_data_records(site_dict)		
						self.get_meta_data_records_for_harvester(site_dict)

						start_response('200 ok', [('Content-Type', 'text/html')])
						return ['<b>ALIVE<BR>' + request + '</b>']
					except Exception, e:
						start_response('400 Bad Request', [('Content-Type', 'text/html')])
						return ['<b>ERROR IN HARVESTER, CHECK CONNECTION<BR>' + request + '<br>' + output + '</b>']				
					
					
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
		r = requests.get(self.GEONETWORK_SERVER+'/geonetwork/srv/eng/harvesting/xml.harvesting.get',auth=("admin","admin"),headers=headers)
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

	def get_meta_data_records_for_harvester(self,site_dict):
		records =[]
		try:
			conn = psycopg2.connect(database=self.GEONETWORK_DB, user=self.GEONETWORK_USER, password=self.GEONETWORK_PASS,host=self.GEONETWORK_DB_SERVER)
			cursor = conn.cursor()
			# execute our Query
			for site_uuid in site_dict.keys():
				cursor.execute("SELECT uuid,data from metadata WHERE harvestuuid='"+site_uuid+"' ")
				records = cursor.fetchall()
				print "number of records...",len(records)
				for rec in records:
					uuid = rec[0]
					soup = BeautifulSoup(rec[1])
					#get the identification information for the place
					rec_name = uuid
					rec_descrip = ""
					try:						
						rec_name = self.getnameinfo(soup)
						rec_descrip = self.getidentinfo(soup)            
						self.getKeyWords(soup)
						self.getGeoExtent(soup)
						dt = self.getTemporalExtent(soup)
						print rec_name,rec_descrip
					except Exception, e:
						print "error getting nodes:",e,"\nUSING:",rec_name,"\n",rec_descrip

					#add the data to the RR	
					self.request_and_create_resource('resource_registry', 'create', object ={"name":rec_name, "description":rec_descrip , "type_":"ExternalDataset"})	

		except Exception, e:
			print e,": I am unable to connect to the database..."
			pass

	def request_and_create_resource(self,service_name, op, **kwargs):
		url = self.SGS_URL
		url = url + service_name + '/' + op
		r = { "serviceRequest": { 
				"serviceName" : service_name, 
				"serviceOp" : op, 
				"params" : kwargs
				}
			}


		resp = requests.post(url, data={'payload':Serializer.encode(r)})
		if resp.status_code == 200:
			data = resp.json()
			if 'GatewayError' in data['data']:
				#error = GatewayError(data['data']['Message'])
				#error.trace = data['data']['Trace']
				#raise error
				pass
			if 'GatewayResponse' in data['data']:
				#return data['data']['GatewayResponse']
				pass

		#raise ConnectionError("HTTP [%s]" % resp.status_code)		
	def getnameinfo(self,soup):
		ab_info = soup.find("gmd:abstract")
		pur_info = soup.find("gmd:purpose")
		file_ident = soup.find("gmd:fileidentifier")
		return file_ident.text.replace("\n","")

	def getidentinfo(self,soup):
		indent_info = soup.find("gmd:identificationinfo")
		title = indent_info.find("gmd:title").text.rstrip()
		alt_title = indent_info.find("gmd:alternatetitle").text.replace("\n","")
		iden = indent_info.find("gmd:identifier").text.replace("\n","")
		org_name = indent_info.find("gmd:organisationname").text.replace("\n","")
		poc = indent_info.find("gmd:pointofcontact")
		return title

	def getKeyWords(self,soup):
		keywords = soup.find("gmd:md_keywords")
		deskeywords = soup.find("gmd:descriptivekeywords")


    
	def getGeoExtent(self,soup):
		bound_list = ["westboundlongitude","eastboundlongitude","northboundlatitude","southboundlatitude"]
		bbox = dict()  
		geo_extent = soup.find("gmd:geographicelement")
		for i in bound_list:
			pos = geo_extent.find("gmd:"+i).text.replace("\n","")
			bbox[i] = float(pos)
		return bbox	

	def getTemporalExtent(self,soup):                       
		temporal_extent = soup.find("gmd:temporalelement")
		start_dt = temporal_extent.find("gml:beginposition").text.replace("\n","")
		end_dt = temporal_extent.find("gml:endposition").text.replace("\n","")
		return [start_dt,end_dt]    


class Serializer:

	@classmethod
	def encode(cls, message):
		return json.dumps(message)

	@classmethod
	def decode(cls, message):
		return json.loads(message, object_hook=cls._obj_hook)

	@classmethod
	def _obj_hook(cls, dct):
		if '__np__' in dct:
			dct = dct['__np__']
			return np.array(dct['data'], dtype=dct['dtype'])
		return dct
