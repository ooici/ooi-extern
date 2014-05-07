#!/usr/bin/python
"""
WSGI geoserver layer server 
"""
from gevent.pywsgi import WSGIServer
from geoserver.catalog import Catalog
from geoserver.layer import Layer
from geoserver.store import coveragestore_from_index, datastore_from_index, \
    DataStore, CoverageStore, UnsavedDataStore, UnsavedCoverageStore
from geoserver.style import Style
from geoserver.support import prepare_upload_bundle
from geoserver.layergroup import LayerGroup, UnsavedLayerGroup
from geoserver.workspace import workspace_from_index, Workspace
from geoserver.resource import FeatureType
from geoserver.support import prepare_upload_bundle, url
import httplib2
import json
import requests
from BeautifulSoup import *
import ast
import yaml
import logging

__author__ = "abird"

# GeoServer
ADDLAYER = "addlayer"
REMOVELAYER = "removelayer"
UPDATELAYER = "updatelayer"
RESETSTORE = "resetstore"
LISTLAYERS = "listlayers"
ALIVE = "alive"

# GeoNetwork
REQUEST_HARVESTER = "requestharvester"
CREATE_HARVESTER = "createharvester"
UPDATE_HARVESTER = "updateharvester"
REMOVE_HARVESTER = "removeharvester"
RESET_HARVESTER = "resetharvester"
START_HARVESTER = "startharvester"
STOP_HARVESTER = "stopharvester"
RUN_HARVESTER = "runharvester"

KEY_SERVICE = 'service'
KEY_NAME = 'name'
KEY_ID = 'id'
PARAMS = 'params'

#load yaml details
class ResourceImporter():
    def __init__(self):
        logger = logging.getLogger('importer_service')
        hdlr = logging.FileHandler('importer_service.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr) 
        logger.setLevel(logging.DEBUG)

        self.logger = logger
        self.logger.info("Setting up geoserver importer service...")

        self.startup()

    def startup(self):
        stream = open("extern.yml", 'r')
        ion_config = yaml.load(stream)
        self.logger.info("opened yml file")

        self.GEO_WS = ion_config['eoi']['geoserver']['geoserver_ooi_workspace']
        self.SERVER = ion_config['eoi']['geoserver']['server']+"/geoserver/rest"
        self.U_NAME = ion_config['eoi']['geoserver']['user_name']
        self.P_WD = ion_config['eoi']['geoserver']['password']
        self.PORT = ion_config['eoi']['importer_service']['port']
        self.GEO_STORE = ion_config['eoi']['geoserver']['geoserver_ooi_store']
        self.SESSION_START_UP_ln1 = ion_config['eoi']['postgres']['session_startup_ln1']
        self.SESSION_START_UP_ln2 = ion_config['eoi']['postgres']['session_startup_ln2']
        
        self.POSTGRES_USER = ion_config['eoi']['postgres']['user_name']
        self.POSTGRES_PASSWORD = ion_config['eoi']['postgres']['password']
        self.POSTGRES_DB = ion_config['eoi']['postgres']['database']
        self.POSTGRES_PORT = ion_config['eoi']['postgres']['port']
        self.POSTGRES_HOST = ion_config['eoi']['postgres']['host']


        self.LAYER_PREFIX = ion_config['eoi']['geoserver']['layer_prefix']
        self.LAYER_SUFFIX = ion_config['eoi']['geoserver']['layer_suffix']

        self.GEONETWORK_BASE_URL = ion_config['eoi']['geonetwork']['base_url']
        self.GEONETWORK_USER = ion_config['eoi']['geonetwork']['user_name']
        self.GEONETWORK_PASS = ion_config['eoi']['geonetwork']['password']
        self.GEONETWORK_ICON = ion_config['eoi']['geonetwork']['icon']

        self.logger.info("parsed attributes")

        self.logger.info('Serving on '+str(self.PORT)+'...')
        server = WSGIServer(('', self.PORT), self.application).serve_forever()

    def application(self, env, start_response):
        request = env['PATH_INFO']
        request = request[1:]
        cat = Catalog(self.SERVER, self.U_NAME, self.P_WD)
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

                #parse request
                if param_dict.has_key(KEY_SERVICE):
                    if param_dict[KEY_SERVICE] == ALIVE:
                        start_response('200 ok', [('Content-Type', 'text/html')])
                        return ['<b>ALIVE<BR>' + request + '<br>' + output + '</b>']
                    elif param_dict[KEY_SERVICE] == ADDLAYER:
                        if param_dict.has_key(KEY_NAME) and param_dict.has_key(KEY_ID):
                            if param_dict.has_key(PARAMS):
                                self.create_layer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS, param_dict[PARAMS])
                            else:
                                start_response('400 Bad Request', [('Content-Type', 'text/html')])
                                return ['<b>ERROR NO PARAMS<BR>' + request + '<br>' + output + '</b>']
                        else:
                            start_response('400 Bad Request', [('Content-Type', 'text/html')])
                            return ['<b>ERROR NO ID or NAME<BR>' + request + '<br>' + output + '</b>']

                    elif param_dict[KEY_SERVICE] == REMOVELAYER:
                        if param_dict.has_key(KEY_NAME) and param_dict.has_key(KEY_ID):
                            self.remove_layer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS, cat)

                    elif param_dict[KEY_SERVICE] == UPDATELAYER:
                        self.remove_layer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS, cat)
                        self.createLayer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS, param_dict[PARAMS])
                        self.logger.info(UPDATELAYER)

                    elif param_dict[KEY_SERVICE] == LISTLAYERS:
                        layer_list_ret = self.get_layer_list(cat)
                        self.logger.info(UPDATELAYER)
                        self.logger.info(layer_list_ret)
                        output = ''.join(layer_list_ret)
                        self.logger.info(output)

                    elif param_dict[KEY_SERVICE] == RESETSTORE:
                        self.reset_data_store(cat)

                    # GeoNetwork Service Calls
                    #
                    # Obtain list of current harvesters, i.e. is the service ALIVE?
                    elif param_dict[KEY_SERVICE] == REQUEST_HARVESTER:
                        r = requests.get(self.GEONETWORK_BASE_URL + 'xml.harvesting.get', auth=(self.GEONETWORK_USER, self.GEONETWORK_PASS))
                        if r.status_code == 200:
                            output = str(r.text)
                            start_response('200 ok', [('Content-Type', 'text/html')])

                            nodes = self.get_geonetwork_nodes(r.text)
                            if len(nodes) >= 1:
                                return ['<b>ALIVE<BR>' + request + '<br>' + output + '</b>']
                            else:
                                return ['<b>ALIVE - NO HARVESTER NODES DEFINED<BR>' + request + '<br>' + output + '</b>']
                        else:
                            start_response(str(r.status_code), [('Content-Type', 'text/html')])
                            return ['<b>ERROR</b>']

                    # Create new harvester
                    elif param_dict[KEY_SERVICE] == CREATE_HARVESTER:
                        # TODO: Check that harvester doesn't already exist (use name field from RR and GN harvester name)
                        # TODO: If it does, make sure to update with new params by DROP/ADD method

                        # Make sure the service is ALIVE
                        r_check = requests.get(self.GEONETWORK_BASE_URL + 'xml.harvesting.get',
                                               auth=(self.GEONETWORK_USER, self.GEONETWORK_PASS))

                        required_parameters = {
                            'id': None,                         # id=6a9e7082c36b4facb915e36488376328
                            #'ownerid': None,
                            'lcstate': None,                    # lcstate=DEPLOYED&
                            #'org_ids': None,
                            #'providerids': None,
                            'externalize': None,                # externalize=0&
                            'name': None,                       # name=ooi&
                            'description': None,                # description=OOI&
                            'datasourcetype': None,             # datasourcetype=sos&
                            'harvestertype': None,              # harvestertype=ogcwxs&
                            'searchterms': None,                # searchterms=&
                            'importxslt': None,                 # importxslt=&
                            'ogctype': None,                    # ogctype=SOS1.0.0&
                            'connectionparams': None,           # connectionparams={}&
                            'datasourceattributes': None,       # datasourceattributes={}&
                            'protocoltype': None,               # institution={'website': '', 'phone': '', 'name': '', 'email': ''}&
                            'institution': None                 # protocoltype=&
                            #'contact': None
                        }

                                                                # rev=1&
                                                                # availability=AVAILABLE&
                                                                # persistedversion=1&
                                                                # addl={}&
                                                                # visibility=1&
                                                                # tsupdated=1399467966285&
                                                                # tscreated=1399467966285&
                                                                # altids=['PRE:EDSID3']&

                        for required_parameter in required_parameters:
                            if required_parameter in param_dict:
                                required_parameters[required_parameter] = param_dict[required_parameter]
                            else:
                                self.logger.warn('Parameter %s is missing.' % required_parameter)

                        # if r_check.status_code == 200 and None not in required_parameters.values():
                        if r_check.status_code == 200:
                            #Set the proper XML payload based on the type and configuration of the harvester
                            payload = self.configure_xml_harvester_add_xml(required_parameters, self.GEONETWORK_ICON)

                            # Check to ensure the XML payload returned properly
                            if payload is not False:
                                headers = {'Content-Type': 'application/xml'}
                                r = requests.post(self.GEONETWORK_BASE_URL + 'xml.harvesting.add',
                                                  data=payload,
                                                  headers=headers,
                                                  auth=(self.GEONETWORK_USER, self.GEONETWORK_PASS))

                                if r.status_code == 200:
                                    output = str(r.text)
                                    start_response('200 ok', [('Content-Type', 'text/html')])
                                    #return ['<b>ALIVE & ADDED<BR>' + request + '<br>' + output + '</b>']
                                    return ['<b>ALIVE & ADDED<br>' + request + '</b></br>' + output]
                            else:
                                # XML payload configuration failed
                                self.logger.error("XML payload configuration failed")
                        else:
                            start_response(str(r_check.status_code), [('Content-Type', 'text/html')])
                            response_str = '<b>ERROR: %s Creating Harvester</b></br>' % r_check.status_code
                            for p in required_parameters:
                                response_str += '%s </br>' % p
                            return [response_str]

                    # Update existing harvester
                    elif param_dict[KEY_SERVICE] == UPDATE_HARVESTER:
                        # TODO: This should be a DROP/ADD
                        pass

                    # Remove existing harvester
                    elif param_dict[KEY_SERVICE] == REMOVE_HARVESTER:
                        pass

                    # Remove ALL harvesters associated with external observatories
                    elif param_dict[KEY_SERVICE] == RESET_HARVESTER:
                        # param_dict can handle a 'mode' of:
                        # all = All harvesters in GeoNetwork
                        # ooi = Only OOI harvesters are selected
                        # and 'action' of:
                        # remove = Remove the chosen harvester(s)
                        # list = Show the harvester that would be removed but take no action

                        # Possible Scenarios
                        # &mode=all&action=remove
                        # &mode=all&action=list
                        # &mode=ooi&action=remove
                        # &mode=ooi&action=list

                        # Check that the mode is set
                        mode = None
                        if 'mode' in param_dict:
                            mode = param_dict['mode']

                        # Check that the action is set
                        action = None
                        if 'action' in param_dict:
                            action = param_dict['action']

                        harvesters, r = self.get_harvesters()

                        start_response(str(r.status_code), [('Content-Type', 'text/html')])

                        response_str = ''
                        if mode is not None and action is not None:
                            if mode == 'all' and action == 'list':
                                # List all node info
                                for harvester in harvesters:
                                    for h in harvesters[harvester]:
                                        response_str += h + ' = ' + harvesters[harvester][h] + '</br>'
                                        print h + ' = ' + harvesters[harvester][h] + '</br>'
                                return [response_str]
                            elif mode == 'all' and action == 'remove':
                                # Remove all nodes
                                response_str = '<b>Not yet implemented, sorry. </b>'
                                return [response_str]
                            elif mode == 'ooi' and action == 'list':
                                # List all OOI nodes
                                # TODO: Need list of OOI node names to compare against like ooi_names
                                ooi_names = ['Neptune SOS']
                                for harvester in harvesters:
                                    for h in harvesters[harvester]:
                                        if harvesters[harvester]['name'] in ooi_names:
                                            response_str += h + ' = ' + harvesters[harvester][h] + '</br>'
                                            print h + ' = ' + harvesters[harvester][h] + '</br>'
                                return [response_str]
                            elif mode == 'ooi' and action == 'remove':
                                # Remove only the OOI nodes
                                response_str = '<b>Not yet implemented, sorry. </b>'
                                return [response_str]
                            else:
                                response_str = 'Could not determine action to perform based on mode/action parameter inputs!</br>'
                                response_str += '<b></br>Possible Scenarios</br></b>'
                                response_str += '&mode=all&action=remove</br>'
                                response_str += '&mode=all&action=list</br>'
                                response_str += '&mode=ooi&action=remove</br>'
                                response_str += '&mode=ooi&action=list</br>'
                                self.logger.warn(response_str)
                                return[response_str]
                        else:
                            response_str = 'Could not determine action to perform based on mode/action parameter inputs!</br>'
                            response_str += '<b></br>Possible Scenarios</br></b>'
                            response_str += '&mode=all&action=remove</br>'
                            response_str += '&mode=all&action=list</br>'
                            response_str += '&mode=ooi&action=remove</br>'
                            response_str += '&mode=ooi&action=list</br>'
                            self.logger.warn(response_str)
                            return[response_str]


                    # Start automated harvester based on defined scheduled time
                    elif param_dict[KEY_SERVICE] == START_HARVESTER:
                        start_response('200 ok', [('Content-Type', 'text/html')])
                        response_str = '<b>Not yet implemented, sorry. </b>'
                        return [response_str]

                    # Stop harvester
                    elif param_dict[KEY_SERVICE] == STOP_HARVESTER:
                        start_response('200 ok', [('Content-Type', 'text/html')])
                        response_str = '<b>Not yet implemented, sorry. </b>'
                        return [response_str]

                    # Run harvester on-demand)
                    elif param_dict[KEY_SERVICE] == RUN_HARVESTER:
                        start_response('200 ok', [('Content-Type', 'text/html')])
                        response_str = '<b>Not yet implemented, sorry. </b>'
                        return [response_str]

        start_response('200 OK', [('Content-Type', 'text/html')])
        return ['<b>' + request + '<br>' + output + '</b>']

    def get_harvesters(self):
        harvesters = {}
        try:
            r = requests.get(self.GEONETWORK_BASE_URL + 'xml.harvesting.get', auth=('admin', 'admin'))
            if r.status_code == 200:
                soup = BeautifulSoup(r.text)
                nodes = soup.findAll('node')
                for node in nodes:
                    hid = str(node['id'])
                    htype = str(node['type'])
                    site = node.find('site')
                    name = str(site.find('name').text)
                    uuid = str(site.find('uuid').text)
                    harvesters[hid] = {'type': htype, 'name': name, 'uuid': uuid}
            return harvesters, r
        except IOError:
            self.logger.error('Could not retrieve harvester node list!')

    def get_geonetwork_nodes(self, response_xml):
        soup = BeautifulSoup(response_xml)
        nodes = soup.findAll("node")
        return nodes

    def get_geo_store_params(self,):
        #rpsdev = 'Session startup SQL': 'select runCovTest();\nselect 1 from covtest limit 1;',
        session_startup = ""
        if self.SESSION_START_UP_ln1 is not None:
            session_startup+=self.SESSION_START_UP_ln1 + '\n'
        if self.SESSION_START_UP_ln2 is not None:
            session_startup += self.SESSION_START_UP_ln2
            
        params = {
            'Connection timeout': '20',
            'Estimated extends': 'true',
            'Expose primary keys': 'false',
            'Loose bbox': 'true', 
            'Session startup SQL': session_startup,
            'Max open prepared statements': '50',
            'database': str(self.POSTGRES_DB),
            'dbtype': 'postgis',
            'encode functions': 'false',
            'fetch size': '1000',
            'host': str(self.POSTGRES_HOST),
            'max connections': '10',
            'min connections': '1',
            'namespace': 'http://www.geonode.org/',
            'port': str(self.POSTGRES_PORT),
            'preparedStatements': 'false',
            'schema': 'public',
            'user': str(self.POSTGRES_USER),
            'validate connections': 'true'
        }
        return params

    def get_layer_list(self, cat):
        layer_list = []
        layer_list.append('List Of DataLayers')
        layer_list.append('<br>')
        layer_list.append('<br>')
        geo_ws = cat.get_workspace(self.GEO_WS)
        try:
            geo_store = cat.get_store(self.GEO_STORE)
            for d in geo_store.get_resources():
                layer_list.append(d.name)
                layer_list.append('<br>')
        except Exception, e:
            self.logger.info("issue getting layers:" + str(e))

        return layer_list    

    def reset_data_store(self, cat):
        self.logger.info(RESETSTORE)
        geo_ws = cat.get_workspace(self.GEO_WS)
        try:
            geo_store = cat.get_store(self.GEO_STORE)
            #remove all the things if it has resources
            for d in geo_store.get_resources():
                layer = cat.get_layer(d.name)
                if layer:
                    #delete the layer
                    cat.delete(layer)
                    #delete the actual file
                    cat.delete(d)
                else:
                    try:
                        self.logger.info("layer thinks it does not exist...remove")
                        cat.delete(d)      
                        pass
                    except Exception, e:
                        self.logger.info("issue getting/removing layer:"+str(e))
                    

            cat.save(geo_store)
            cat.delete(geo_store)
        except Exception,e:
            self.logger.info("issue getting/removing datastore:"+str(e))

        try:
            if cat.get_store(self.GEO_STORE):
                #store exists for some reason was not removed!?
                self.logger.info("using existing datastore")
        except Exception, e:
            self.logger.info("create new")
            #store does not exist create it, the preferred outcome
            geo_store = cat.create_datastore(self.GEO_STORE, geo_ws)
            geo_store.capabilitiesURL = "http://www.geonode.org/"
            geo_store.type = "PostGIS"
            geo_store.connection_parameters = self.get_geo_store_params()
            #MUST SAVE IT!
            info = cat.save(geo_store)
            self.logger.info(info[0]['status']+" store created...")

    def remove_layer(self,layer_name, store_name, workspace_name, cat):
        self.logger.info (REMOVELAYER)

        geo_ws = cat.get_workspace(self.GEO_WS)
        try:
            geo_store = cat.get_store(self.GEO_STORE)
            #remove all the things if it has resources
            layer = cat.get_layer(layer_name)
            if (layer):
                #delete the layer
                cat.delete(layer)
                #delete the actual file/resource
                cat.delete(cat.get_resource(layer_name))
                cat.save(geo_store)
            #else:
                #if the layer does not exist try deleting the resource
            #    cat.delete(cat.get_resource(layer_name))
            #    cat.save(geo_store)

        except Exception:
            self.logger.info("issue getting/removing data layer/resource")

    def create_layer(self, layer_name, store_name, workspace_name, params):
        self.logger.info(ADDLAYER)
        xml = '''<?xml version='1.0' encoding='utf-8'?>
            <featureType>
    		  <name>%s%s%s</name>
    		  <nativeName>layer_%s</nativeName>
    		  <namespace>
    		    <name>%s</name>
    		    <atom:link xmlns:atom="http://www.w3.org/2005/Atom\" rel=\"alternate\" href=\"http://localhost:8080/geoserver/rest/namespaces/geonode.xml\" type=\"application/xml\"/>
    		  </namespace>
    		  <title>DataProductLayer</title>
    		  <keywords>
    		    <string>DataProductLayer</string>
    		    <string>autoGeneration</string>
    		  </keywords>
    		  <srs>EPSG:4326</srs>
    		  <nativeBoundingBox>
    		    <minx>-180</minx>
                <maxx>180</maxx>
                <miny>-90.0</miny>
                <maxy>90.0</maxy>
    		  </nativeBoundingBox>
    		  <latLonBoundingBox>
    		    <minx>-180</minx>
                <maxx>180</maxx>
                <miny>-90.0</miny>
                <maxy>90.0</maxy>
    		  </latLonBoundingBox>
    		  <projectionPolicy>FORCE_DECLARED</projectionPolicy>
    		  <enabled>true</enabled>
    		  <metadata>
                <entry key="time">
                    <dimensionInfo>
                        <enabled>true</enabled>
                        <attribute>time</attribute>
                        <presentation>LIST</presentation>
                        <units>ISO8601</units>
                    </dimensionInfo>
                </entry>
                <entry key="elevation">
                    <dimensionInfo>
                    <enabled>false</enabled>
                    </dimensionInfo>
                </entry>
    		    <entry key=\"cachingEnabled\">false</entry>
    		    <entry key=\"JDBC_VIRTUAL_TABLE\">
    		      <virtualTable>
    		        <name>layer_%s</name>
    		        <sql>select * from _%s_view</sql>
    		        <escapeSql>false</escapeSql>
                    <geometry>
                    <name>geom</name>
                    <type>Point</type>
                    <srid>4326</srid>
                    </geometry>
    		      </virtualTable>
    		    </entry>
    		  </metadata>
    		  <store class=\"dataStore\">
    		    <name>%s</name>
    		    <atom:link xmlns:atom=\"http://www.w3.org/2005/Atom\" rel=\"alternate\" href=\"http://localhost:8080/geoserver/rest/workspaces/geonode/datastores/ooi.xml\" type=\"application/xml\"/>
    		  </store>
    		  <maxFeatures>0</maxFeatures>
    		  <numDecimals>0</numDecimals>
    		  '''% (self.LAYER_PREFIX, layer_name, self.LAYER_SUFFIX ,layer_name, workspace_name, layer_name, layer_name, store_name)
              
        xml += "<attributes>"

        #log.info("------------------\n")
        params = ast.literal_eval(params)
        #add point geom
        params['geom'] = "geom"
        self.logger.info (params)
        #log.info("------------------\n")

        #add attribute list
        for paramItem in params:
            xml += self.add_attributes(paramItem,params[paramItem])

        xml += "</attributes>"
        xml += "</featureType>"
        #generate layer
        serverpath = str(self.SERVER) + "/" + "workspaces" + "/" + self.GEO_WS + "/" + "datastores/"+self.GEO_STORE+"/featuretypes" 
        headers = {'Content-Type': 'application/xml'} # set what your server accepts
        auth = (str(self.U_NAME), str(self.P_WD))

        r = requests.post(serverpath,
                         data=xml, 
                         headers=headers,
                         auth=auth)

        self.logger.info("statusCode:"+str(r.status_code))

        #log.info r.text
        layer_name = self.LAYER_PREFIX+layer_name+self.LAYER_SUFFIX
        #append query 
        serverpath = self.SERVER+"/layers/"+layer_name+'.xml'
        r = requests.get(serverpath,
                     headers=headers,
                     auth=auth)

        #get the existing layer
        self.logger.info("statusCode: getLayer:"+str(r.status_code))
        if r.status_code == 200:
            xml = r.text
            findString = ('</resource>')
            val= xml.find(findString)
            xmlPart1 = xml[:val+len(findString)]
            xmlAgg = xmlPart1+"\n<queryable>true</queryable>"+xml[val+len(findString):]
            #log.info "-----------"
            #log.info xmlAgg
            r = requests.put(serverpath,
                             data=xmlAgg, 
                             headers=headers,
                             auth=auth)

            self.logger.info("statusCode: updateLayer:"+str(r.status_code))
        else:
            self.logger.info("could not get layer, check it exists... "+r.text)    
        pass

    def add_attributes(self, param, param_type):

        attribute = "<attribute>"
        attribute += "<name>"+param+"</name>"
        attribute += "<minOccurs>0</minOccurs>"
        attribute += "<maxOccurs>1</maxOccurs>"
        attribute += "<nillable>true</nillable>"
        
        if param == "geom":
            attribute += "<binding>com.vividsolutions.jts.geom.Point</binding>"
        elif param_type == "float":
            attribute += "<binding>java.lang.Float</binding>"
        elif param_type == "real":
            attribute += "<binding>java.lang.Float</binding>"  
        elif param_type == "time":
            attribute += "<binding>java.sql.Timestamp</binding>" 
        elif param_type == "int":
            attribute += "<binding>java.lang.Int</binding>"            
        else:
            attribute += "<binding>java.lang.Float</binding>"

        attribute += "</attribute>"

        return attribute

    def configure_xml_harvester_add_xml(self, required_parameters, icon):
        # Validate required_parameters values
        valid_parameters = True

        harvester_types = [
            'geonetwork',
            'webdav',
            'csw',
            'z3950',
            'oaipmh',
            'thredds',
            'wfsfeatures',
            'filesystem',
            'arcsde',
            'ogcwxs',
            'geoPREST'
        ]

        if None in required_parameters:
            valid_parameters = False

        if required_parameters['harvestertype'] not in harvester_types:
            valid_parameters = False

        # Search term management
        xmlTemplate = """<search>
            <freeText>%s</freeText>
        </search>"""
        search_terms = required_parameters['searchterms'].split(',')
        searches = ''
        if len(required_parameters['searchterms']) > 0:
            for search_term in search_terms:
                searches += xmlTemplate % search_term
                searches += '\n'
        else:
            searches = xmlTemplate % ''

        # Gather all parameters for XML file
        other_parameters = {}
        other_parameters['searches'] = searches
        other_parameters['icon'] = icon
        other_parameters['baseurl'] = required_parameters['protocoltype']

        xmldata = required_parameters.copy()
        xmldata.update(other_parameters)

        if valid_parameters:
            # GeoPortal (geoPREST) Harvester XML
            # TODO: This is the only one supported at the moment
            if required_parameters['harvestertype'] == 'geoPREST':
                xml = '''<?xml version='1.0' encoding='utf-8'?>
                <node type=\"%(harvestertype)s\">
                    <owner>
                        <id>1</id>
                    </owner>
                    <ownerGroup>
                        <id>3</id>
                    </ownerGroup>
                    <site>
                        <name>%(name)s</name>
                        <account>
                            <use>true</use>
                            <username/>
                            <password/>
                        </account>
                        <baseUrl>%(baseurl)s</baseUrl>
                        <icon>%(icon)s</icon>
                    </site>
                    <content>
                        <validate>false</validate>
                        <importxslt>%(importxslt)s</importxslt>
                    </content>
                    <options>
                        <every>0 0 0 ? * *</every>
                        <oneRunOnly>true</oneRunOnly>
                        <status>inactive</status>
                    </options>
                    <searches>
                        %(searches)s
                    </searches>
                    <privileges>
                        <group id=\"3\">
                            <operation name=\"view\" />
                            <operation name=\"dynamic\" />
                            <operation name=\"featured\" />
                        </group>
                    </privileges>
                    <categories>
                        <category id="2" />
                    </categories>
                </node>''' % xmldata
                print xml
                return xml
            elif required_parameters['harvestertype'] == 'ogcwxs':
                xml = ''
                return xml
            else:
                return False
        else:
            self.logger.error('Could not create harvester XML definition based on supplied input!')
            return False

