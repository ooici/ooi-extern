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
import ast
import yaml
from pyon.util.log import log

from pyon.core import config, bootstrap

__author__ = "abird"

ADDLAYER = "addlayer"
REMOVELAYER = "removelayer"
UPDATELAYER = "updatelayer"
RESETSTORE = "resetstore"
LISTLAYERS = "listlayers"
ALIVE = "alive"

KEY_SERVICE = 'service'
KEY_NAME = 'name'
KEY_ID = 'id'
PARAMS = 'params'

#load yaml details
class ResourceImporter():
    def __init__(self):
        pyon_config = config.read_standard_configuration()      # Initial pyon.yml + pyon.local.yml
        log.info("Setting up geoserver importer service...")
        self.startup()

    def startup(self):

        ion_config = config.read_standard_configuration()
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

        log.info('Serving on '+str(self.PORT)+'...')
        server = WSGIServer(('', self.PORT), self.application).serve_forever()

    def application(self,env, start_response):
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
                if (param_dict.has_key(KEY_SERVICE)):
                    if (param_dict[KEY_SERVICE] == ALIVE):
                         start_response('200 ok', [('Content-Type', 'text/html')])
                         return ['<b>ALIVE<BR>' + request + '<br>'+ output +'</b>']
                    elif (param_dict[KEY_SERVICE] == ADDLAYER):
                        if (param_dict.has_key(KEY_NAME) and param_dict.has_key(KEY_ID)):
                            if param_dict.has_key(PARAMS):
                                self.create_layer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS,param_dict[PARAMS])
                            else:
                                start_response('400 Bad Request', [('Content-Type', 'text/html')])
                                return ['<b>ERROR NO PARAMS<BR>' + request + '<br>'+ output +'</b>']    
                        else:
                            start_response('400 Bad Request', [('Content-Type', 'text/html')])
                            return ['<b>ERROR NO ID or NAME<BR>' + request + '<br>'+ output +'</b>']    

                    elif (param_dict[KEY_SERVICE] == REMOVELAYER):
                        if (param_dict.has_key(KEY_NAME) and param_dict.has_key(KEY_ID)):
                            self.remove_layer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS,cat)

                    elif (param_dict[KEY_SERVICE] == UPDATELAYER):
                        self.remove_layer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS,cat)
                        self.createLayer(param_dict[KEY_NAME], self.GEO_STORE, self.GEO_WS,param_dict[PARAMS])
                        log.info(UPDATELAYER)

                    elif (param_dict[KEY_SERVICE] == LISTLAYERS):
                        layer_list_ret = self.get_layer_list(cat)
                        log.info(UPDATELAYER)
                        log.info(layer_list_ret)
                        output = ''.join(layer_list_ret)
                        log.info(output)

                    elif (param_dict[KEY_SERVICE] == RESETSTORE):
                       self.reset_data_store(cat)

        start_response('200 OK', [('Content-Type', 'text/html')])
        return ['<b>' + request + '<br>'+ output +'</b>']


    def get_geo_store_params(self,):
        #rpsdev = 'Session startup SQL': 'select runCovTest();\nselect 1 from covtest limit 1;',
        session_startup =""
        if (self.SESSION_START_UP_ln1 is not None):
            session_startup+=self.SESSION_START_UP_ln1 + '\n'
        if (self.SESSION_START_UP_ln2 is not None):
            session_startup+=self.SESSION_START_UP_ln2
            
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

    def get_layer_list(self,cat):
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
        except Exception,e:
            log.info("issue getting layers:"+str(e))

        return layer_list    


    def reset_data_store(self,cat):
        log.info(RESETSTORE)
        geo_ws = cat.get_workspace(self.GEO_WS)
        try:
            geo_store = cat.get_store(self.GEO_STORE)
            #remove all the things if it has resources
            for d in geo_store.get_resources():
                layer = cat.get_layer(d.name)
                if (layer):
                    #delete the layer
                    cat.delete(layer)
                    #delete the actual file
                    cat.delete(d)
                else:
                    try:
                        log.info("layer thinks it does not exist...remove")
                        cat.delete(d)      
                        pass
                    except Exception, e:
                        log.info("issue getting/removing layer:"+str(e))
                    

            cat.save(geo_store)
            cat.delete(geo_store)
        except Exception,e:
            log.info("issue getting/removing datastore:"+str(e))

        try:
            if (cat.get_store(self.GEO_STORE)):
                #store exists for some reason was not removed!?
                log.info("using existing datastore")
        except Exception, e:
            log.info("create new")
            #store does not exist create it, the prefered outcome 
            geo_store = cat.create_datastore(self.GEO_STORE, geo_ws)
            geo_store.capabilitiesURL = "http://www.geonode.org/"
            geo_store.type = "PostGIS"
            geo_store.connection_parameters = self.get_geo_store_params()
            #MUST SAVE IT!
            info = cat.save(geo_store)
            log.info(info[0]['status']+" store created...")

    def remove_layer(self,layer_name, store_name, workspace_name, cat):
        log.info (REMOVELAYER)

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
            log.info("issue getting/removing data layer/resource")

    def create_layer(self,layer_name, store_name, workspace_name,params):
        log.info(ADDLAYER)
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
    		  '''% (self.LAYER_PREFIX,layer_name, self.LAYER_SUFFIX ,layer_name,workspace_name, layer_name , layer_name, store_name)
              
        xml += "<attributes>"

        #log.info("------------------\n")
        params = ast.literal_eval(params)
        #add point geom
        params['geom'] = "geom"
        log.info (params)
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

        log.info("statusCode:"+str(r.status_code))

        #log.info r.text
        layer_name = self.LAYER_PREFIX+layer_name+self.LAYER_SUFFIX
        #append query 
        serverpath = self.SERVER+"/layers/"+layer_name+'.xml'
        r = requests.get(serverpath,
                     headers=headers,
                     auth=auth)

        #get the existing layer
        log.info("statusCode: getLayer:"+str(r.status_code))
        if (r.status_code==200):
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

            log.info("statusCode: updateLayer:"+str(r.status_code))
        else:
            log.info("could not get layer, check it exists... "+r.text)    
        pass

    def add_attributes(self,param,param_type):

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

