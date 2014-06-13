#!/usr/bin/python
"""
WSGI GeoNetwork to OOI Resource Registry Metadata Synchronization Service
"""
from gevent.pywsgi import WSGIServer
import httplib2
import json
import requests
from bs4 import BeautifulSoup
import yaml
import logging
import psycopg2
import simplejson as json
import numpy as np

__author__ = "abird"

# USAGE: See the following for reference:
# http://geonetwork-opensource.org/manuals/trunk/eng/developer/xml_services/metadata_xml_search_retrieve.html#search-metadata-xml-search

# Content headers
headers = {'content-type': 'application/xml'}

SYNC_HARVESTERS = "syncharvesters"
ALIVE = "alive"

KEY_SERVICE = 'service'
KEY_NAME = 'name'
KEY_ID = 'id'
PARAMS = 'params'


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

        self.RR_PORT = ion_config['eoi']['resync_service']['port']
        self.SGS_URL = self.url = ion_config['eoi']['resync_service']['sgs_url']
        self.HARVESTER_LIST = self.url = ion_config['eoi']['resync_service']['harvester_list']

        self.GEONETWORK_BASE_URL = ion_config['eoi']['geonetwork']['base_url']
        self.GEONETWORK_USER = ion_config['eoi']['geonetwork']['user_name']
        self.GEONETWORK_PASS = ion_config['eoi']['geonetwork']['password']

        self.NEPTUNE_URL = "http://dmas.uvic.ca/DeviceListing?DeviceId="

        self.GEONETWORK_DB_SERVER = ion_config['eoi']['geonetwork']['database_server']
        self.GEONETWORK_DB_NAME = ion_config['eoi']['geonetwork']['database_name']
        self.GEONETWORK_DB_USER = ion_config['eoi']['geonetwork']['database_user']
        self.GEONETWORK_DB_PASS = ion_config['eoi']['geonetwork']['database_password']

        self.EXTERNAL_CATEGORY = 3

        self.logger.info('Serving on '+str(self.RR_PORT)+'...')
        print ('Serving on '+str(self.RR_PORT)+'...')
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

                if param_dict.has_key(KEY_SERVICE):
                    if param_dict[KEY_SERVICE] == ALIVE:
                        start_response('200 ok', [('Content-Type', 'text/html')])
                        return ['<b>RESYNC SERVICE IS ALIVE<BR>' + request + '<br>' + output + '</b>']
                    elif param_dict[KEY_SERVICE] == SYNC_HARVESTERS:
                        try:
                            self.logger.info("requested sync harvesters:")
                            site_dict = self.get_harvester_list()
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
        """
        Creates a dict of valid harvester names and id's using GeoNetwork's XML REST service
        """
        site_dict = dict()
        try:    
            self.logger.info("accessing: "+self.GEONETWORK_BASE_URL)
            r = requests.get(self.GEONETWORK_BASE_URL+'xml.harvesting.get', auth=(self.GEONETWORK_USER, self.GEONETWORK_PASS), headers=headers)                        
            soup = BeautifulSoup(r.text)            
            site_list = soup.find_all("site")            
            #accept_list = self.HARVESTER_LIST #removed as ioos names will be added via the catalog
            for site in site_list:
                name = site.find("name").text               
                uuid = site.find("uuid").text
                site_dict[uuid] = name
            return site_dict

        except Exception, e:
            self.logger.info("accessing error: "+str(e))

    def get_meta_data_records_for_harvester(self, site_dict):
        """
        Lookup and extract metadata records from GeoNetwork and add to the RR
        """        
        self.logger.info("getting meta data records for harvester...")
        try:
            conn = psycopg2.connect(database=self.GEONETWORK_DB_NAME, user=self.GEONETWORK_DB_USER, password=self.GEONETWORK_DB_PASS, host=self.GEONETWORK_DB_SERVER)
            cursor = conn.cursor()
            self.logger.info("SQL cursor obtained...")
            # execute our Query            
            for site_uuid in site_dict.keys():                
                cursor.execute("SELECT m.uuid,m.changedate,mr.registerdate,mr.rruuid,m.changedate NOT LIKE mr.registerdate AS mchanged FROM metadata m FULL JOIN metadataregistry mr ON m.uuid=mr.gnuuid WHERE m.harvestuuid='" + site_uuid + "'")
                records = []
                records = cursor.fetchall()
                self.logger.info("Number of records for harvester"+ site_dict[site_uuid]+ ": " + str(len(records)))
                for rec in records:
                    try: 
                        uuid = rec[0]

                        # Get the metadata record
                        soup = BeautifulSoup(self.get_metadata_payload(uuid))
                        #get the identification information for the place                                     
                        rec_descrip = ""
                    
                        #fix names if they contain invalid characters                   
                        rec_name = self.get_name_info(soup).replace('\\r\\n', "").rstrip()
                        rec_name =  rec_name.replace('\\t', "").strip()

                        rec_descrip = self.get_ident_info(soup).replace('\\r\\n', "").rstrip()
                        rec_descrip =  rec_descrip.replace('\\t', "").strip()                                                                    
                        
                        if rec_name == uuid:
                            rec_name = rec_descrip

                        if site_dict[site_uuid] == "neptune":                            
                            #make the name and description the same
                            rec_descrip = "sensor "+rec_name                            
                            rec_params = self.getkeywords(soup)
                            self.logger.info(str(rec_params))                 
                        else:
                            rec_params = None

                        #self.getgeoextent(soup)
                        #dt = self.get_temporal_extent(soup)
                           
                        # Create RR entries and add/modify/delete lookups in metadataregistry table
                        rec_changedate = rec[1]
                        #rec_registerdate = rec[2]
                        rec_rruuid = rec[3]
                        rec_mchanged = rec[4]                        
                        ref_url = self.get_reference_url(site_dict, site_uuid, uuid,rec_name)

                    except Exception, e:                       
                        self.logger.info('Error getting record from metadata record.'+str(e))
                        continue

                    try:                       
                        #add the data to the RR
                        if rec_rruuid is None:
                            # The metadata record is new
                            data_product_id = self.create_new_resource(uuid,rec_name,rec_descrip,ref_url,rec_params)
                            if data_product_id is None:
                                self.logger.info("resource record was not created in SGS:"+str(data_product_id))
                            else:
                                self.logger.info("new meta data record:"+str(data_product_id))    
                                rruuid = data_product_id                 
                                # Add record to metadataregistry table with registerdate and rruuid
                                insert_values = {'uuid': uuid, 'rruuid': data_product_id, 'changedate': rec_changedate}
                                insert_stmt = "INSERT INTO metadataregistry (gnuuid,rruuid,registerdate) VALUES ('%(uuid)s','%(rruuid)s','%(changedate)s')" % insert_values
                                cursor.execute(insert_stmt)
                                self.logger.info("update meta data registry:"+str(insert_stmt))
                                
                        elif rec_mchanged:    
                            #get the current data product
                            dp = self.request_resource_action('resource_registry', 'read', object_id=rec_rruuid)
                            #update the fields
                            dp["name"] = rec_name
                            dp["description"] = rec_descrip
                            dp["reference_urls"] = [ref_url]
                            # update new resource in the RR
                            self.request_resource_action('resource_registry', 'update', object=dp)

                            # UPDATE metadataregistry table record with updated registerdate and rruuid
                            update_values = {'uuid': uuid, 'rruuid': rec_rruuid, 'changedate': rec_changedate}
                            update_stmt = ("UPDATE metadataregistry SET rruuid='%(rruuid)s', registerdate='%(changedate)s' WHERE gnuuid='%(uuid)s'" % update_values)
                            cursor.execute(update_stmt)

                        elif uuid is None:
                            # Metadata record was deleted by the harvester, cleanup the lookup table and the OOI RR
                            # Delete from RR
                            self.request_resource_action('resource_registry', 'delete', object_id=rec_rruuid)

                            # Delete from metadataregistry
                            delete_values = {'rruuid': rec_rruuid}
                            delete_stmt = ("DELETE FROM metadataregistry WHERE rruuid='%(rruuid)s'" % delete_values)
                            cursor.execute(delete_stmt)
                    except Exception, e:
                        self.logger.info(str(e) + ": error performing sql commands")
        except Exception, e:
            self.logger.info(str(e) + ": I am unable to connect to the database...")

    def generate_param_from_metadata(self,param_item):
        #param should look like this
        
        param_def = {"name" : param_item,
                    "display_name" : param_item,
                    "description" : param_item,
                    "units" : "unknown",
                    "parameter_type" : "quantity",
                    "value_encoding" : "float32",
                    "type_" : "ParameterContext" 
                    }
        
        return param_def

    def create_new_resource(self,uuid,rec_name,rec_descrip,ref_url,params):
        try:        
            #if there are params add them else return
            if params is None:
               #create data product using the information provided
                dp_id,_ = self.request_resource_action('resource_registry', 'create', object={"category":self.EXTERNAL_CATEGORY,
                                                                                                "name": rec_name, 
                                                                                                "ooi_product_name":"External Resource",
                                                                                                "quality_control_level":'Not Applicable',
                                                                                                "processing_level_code":'External L0',
                                                                                                "description": rec_descrip, 
                                                                                                "type_": "DataProduct",
                                                                                                "reference_urls":[ref_url]
                                                                                            })
            else:

                #gets the simple time param id
                simple_time,_ = self.request_resource_action('resource_registry', 'find_resources_ext', **{"alt_id":"PD7", "alt_id_ns":'PRE', "id_only":True})
    
                        
                #create the param dict
                parameter_dictionary_id = self.request_resource_action('dataset_management', 'create_parameter_dictionary', **{"name":uuid, 
                                                                             "parameter_context_ids":simple_time,
                                                                             "temporal_context" : 'time'})

                #create stream def
                stream_def = self.request_resource_action('pubsub_management', 'create_stream_definition', **{"name":uuid, "parameter_dictionary_id":parameter_dictionary_id})


                #create data product using the information provided
                dp_id,_ = self.request_resource_action('resource_registry', 'create', object={"category":self.EXTERNAL_CATEGORY,
                                                                                                "name": rec_name, 
                                                                                                "ooi_product_name":"External Resource",
                                                                                                "quality_control_level":'Not Applicable',
                                                                                                "processing_level_code":'External L0',
                                                                                                "description": rec_descrip, 
                                                                                                "type_": "DataProduct",
                                                                                                "reference_urls":[ref_url]
                                                                                            })
                #join the steam def to the data product
                #this will fail if it is already joined to a stream def (hasStreamDefinition already exists)
                gwresponse = self.request_resource_action('resource_registry', 'create_association', **{"subject":dp_id, 
                                                                                         "predicate":"hasStreamDefinition",
                                                                                         "object" : stream_def
                                                                                         })

                for p in params:
                    #create the param using the param def
                    param_def = self.generate_param_from_metadata(p)

                    param_id = self.request_resource_action('dataset_management', 'create_parameter', parameter_context=param_def)
                    #add the param dict to the data product
                    parameter_dictionary_id = self.request_resource_action('data_product_management', 
                                                                      'add_parameter_to_data_product',
                                                                       **{"parameter_context_id":param_id, 
                                                                      'data_product_id':dp_id
                                                                    })

            return dp_id

        except Exception, e:
            #usually means that the 
            self.logger.info("error creating data product:"+(str(e)))           
            raise e   

    def get_reference_url(self,site_dict,site_uuid,uuid,rec_name):
        ref_url = ""
        if site_dict[site_uuid] == "neptune":
            #split the name to get the sensor id            
            ref_url = self.NEPTUNE_URL+str(rec_name.split(":")[0])
        else:
            ref_url = self.GEONETWORK_BASE_URL+"main.home?uuid="+str(uuid)    
            #self.logger.info("uuid:"+ref_url)

        #fix url encoding issues
        ref_url = ref_url.replace("{","%7B")
        ref_url = ref_url.replace("}","%7D")
        return ref_url

    def get_metadata_payload(self, uuid):
        try: 
            conn = psycopg2.connect(database=self.GEONETWORK_DB_NAME, user=self.GEONETWORK_DB_USER, password=self.GEONETWORK_DB_PASS, host=self.GEONETWORK_DB_SERVER)
            cursor = conn.cursor()   
            get_values = {'uuid': uuid}
            query = "SELECT m.data FROM metadata m WHERE m.uuid='"+uuid+"'"       
            cursor.execute(query)
            record = cursor.fetchall()
            if len(record) == 1:
                return str(record[0])
            else:
                raise ValueError('More than one metadata record was returned.  The metadataregistry table has duplicates!')
            self.logger.info("record: "+record)              
        except Exception, e:
             self.logger.info("error getting data: "+str(e))          

    def request_resource_action(self, service_name, op, **kwargs):  

        url = self.SGS_URL
        url = "/".join([url, service_name, op])
        #self.logger.info("url:"+url)
             
        r = {"serviceRequest": {
            "serviceName": service_name,
            "serviceOp": op,
            "params": kwargs}
        }

        resp = requests.post(url, data={'payload': Serializer.encode(r)})        

        if "<h1>Not Found</h1>" in resp.text:
             self.logger.info("service gateway service not found")     
        else:
            if resp.status_code == 200:
                data = resp.json()
                if 'GatewayError' in data['data']:
                    error = GatewayError(data['data']['Message'])
                    self.logger.info("GATEWAY ERROR:"+str(error))     
                if 'GatewayResponse' in data['data']:
                    return data['data']['GatewayResponse']

    def get_name_info(self, soup):
        ab_info = soup.find("gmd:abstract")
        pur_info = soup.find("gmd:purpose")
        file_ident = soup.find("gmd:fileidentifier")
        return file_ident.text.replace("\n", "")

    def get_ident_info(self, soup):
        indent_info = soup.find("gmd:identificationinfo")
        title = indent_info.find("gmd:title").text.rstrip()
        #alt_title = indent_info.find("gmd:alternatetitle").text.replace("\n", "")
        #iden = indent_info.find("gmd:identifier").text.replace("\n", "")
        #org_name = indent_info.find("gmd:organisationname").text.replace("\n", "")
        #poc = indent_info.find("gmd:pointofcontact")
        return title

    def getkeywords(self, soup):
        keywords = soup.find("gmd:md_keywords")
        params = keywords.findAll('gco:characterstring')
        param_list = []
        for p in params:
            param_list.append(p.text)
        deskeywords = soup.find("gmd:descriptivekeywords")   
        self.logger.info("Number of Params:"+str(len(param_list)))     
        return param_list

    def getgeoextent(self, soup):
        bound_list = ["westboundlongitude", "eastboundlongitude", "northboundlatitude", "southboundlatitude"]
        bbox = dict()
        geo_extent = soup.find("gmd:geographicelement")
        for i in bound_list:
            pos = geo_extent.find("gmd:"+i).text.replace("\n","")
            bbox[i] = float(pos)
        return bbox

    def get_temporal_extent(self, soup):
        temporal_extent = soup.find("gmd:temporalelement")
        start_dt = temporal_extent.find("gml:beginposition").text.replace("\n", "")
        end_dt = temporal_extent.find("gml:endposition").text.replace("\n", "")
        return [start_dt, end_dt]


class Serializer:
    """
    Serializes JSON data
    """

    def __init__(self):
        pass

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
