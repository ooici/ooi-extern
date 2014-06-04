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
from bs4 import BeautifulSoup, Tag, NavigableString
import sys

__author__ = "abird"

class Handler():
    def __init__(self):
        logger = logging.getLogger('importer_service')
        hdlr = logging.FileHandler('importer_service.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr) 
        logger.setLevel(logging.DEBUG)


        self.sos_url = "http://dmas.uvic.ca/sos"

        self.logger = logger
        self.logger.info("Setting up neptune handler service...")

        self.startup()

    def startup(self):
        #depends which dir you are in 
        
        stream = open("extern.yml", 'r')            
        
        ion_config = yaml.load(stream)

        self.PORT = ion_config['eoi']['neptune_sos_handler']['port']
        self.logger.info('Serving Neptune Handler on '+str(self.PORT)+'...')
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
            
            if  len(env['QUERY_STRING']) < 2:
                print "request:"+request
            else:
                request = env['QUERY_STRING']

            output = ''
           
            neptune_sos_link = self.sos_url+"?"+request
            print neptune_sos_link
            r_text = requests.get(neptune_sos_link)

        print "---end of request---"

        
        soup = BeautifulSoup(r_text.text,"xml")   
        obs_offferings = soup.findAll("ObservationOffering")
        total = len(obs_offferings)
        point = total / 100
        increment = total / 20
        i=0
        for obs_offer in obs_offferings:   
            #get the procedure
            link = obs_offer.find("procedure")['xlink:href']

            d = self.describe_sensor_post_request(self.get_describe_sensor_xml(link))        
            sensor_name = self.parse_sensor_name(d[0])
            sensor_description = d[1]
            field_mapping = d[2]

            #get the name
            env = obs_offer.find("Envelope")
            name = obs_offer.find("name").text
            name = name.replace("Offering","")            
            obs_offer.find("name").string = sensor_name
            obs_offer["gml:id"] = sensor_name


            #add description from describe sensor
            destag = BeautifulSoup()
            desc_tag = destag.new_tag("gml:description","")
            desc_tag.string = name+":"+sensor_description
            obs_offer.insert(1, desc_tag)

            for obs_prop in obs_offer.findAll('observedProperty'):
                obs_link = str(obs_prop['xlink:href'])                
                obs_prop['xlink:href'] = field_mapping[obs_link]

            env['srsName'] = "urn:ogc:def:crs:EPSG:6.5:4326" 
           
            sys.stdout.write("\r[" + "=" * (i / increment) +  " " * ((total - i)/ increment) + "]" +  str(i / point) + "%")
            sys.stdout.flush()

            i +=1
            
        response_headers = [('Content-Type', 'application/xml; charset=utf-8')]
        status = '200 OK'
        #remove the html codes i
        html_start = "<html><body>"
        html_end = "</body></html>"
        xm_response = str(soup)
        if xm_response.startswith(html_start):
            xm_response = xm_response.replace(html_start, "")
        if xm_response.endswith(html_end):  
            xm_response = xm_response.replace(html_end,"")

        #add the xml heeader
        #xm_response = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"+xm_response
        print "\n----------------"
        #print "xmlresp:\n"+xm_response[:]
        start_response(status, response_headers)
        return [xm_response]

    def find(self,sensor_string):
        ch = ":"
        data_list = [i for i, ltr in enumerate(sensor_string) if ltr == ch]
        return data_list[-1]

    def parse_sensor_name(self,sensor_id_string):
        sensor_id_string = sensor_id_string.rstrip()
        idx = self.find(sensor_id_string)
        return sensor_id_string[idx+1:].rstrip("\n")

    def describe_sensor_post_request(self,describe_sensor_xml):
        '''
        uses the describe sensor to get some more information about the sensor
        '''
        r = requests.post(self.sos_url, data=describe_sensor_xml)
        soup = BeautifulSoup(r.text)

        info = soup.findAll("term")
        sensor_name = info[0].text
        sensor_description = info[1].text
        #not needed
        sensor_offering_name = info[2].text
        
        #find the props
        input_list = soup.findAll("input")
        obs_list = soup.findAll("ns:observableproperty")
        field_mapping = dict()

        for i in range(0,len(input_list)):
            name = input_list[i]['name']
            definition = obs_list[i]['definition']
            field_mapping[definition] = name
                
        return [sensor_name,sensor_description,field_mapping]


    def get_describe_sensor_xml(self,offering_id):
        xml_describe_obs = '''<?xml version="1.0" encoding="UTF-8"?>
                <DescribeSensor version="1.0.0" service="SOS"
                    xmlns="http://www.opengis.net/sos/1.0"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xsi:schemaLocation="http://www.opengis.net/sos/1.0
                    http://schemas.opengis.net/sos/1.0.0/sosDescribeSensor.xsd"
                    outputFormat="text/xml;subtype=&quot;sensorML/1.0.1&quot;">
                
                    <procedure>%s</procedure></DescribeSensor>''' % (offering_id)

        return xml_describe_obs            
