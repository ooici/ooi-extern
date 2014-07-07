"""
An ION Coverage Foreign Data Wrapper via erddap
"""

__author__ = 'abird'

import sys
import math
import numpy as np
import time
from multicorn import ColumnDefinition
from multicorn import ForeignDataWrapper
from multicorn import Qual
from multicorn.utils import log_to_postgres,WARNING,ERROR
from numpy.random import random
import simplejson as json
import requests
import random
import os 
import datetime
import logging

TIME = 'time'

#size of mock data
cov_fail_data_size = 100
#used for by passing coverage issues and generating mock data
debug = False

SERVER = "http://localhost:8005/erddap/tabledap/"
SGS_URL = "http://localhost:5000/ion-service"
LOG_LOCATION = "/Users/rpsdev/log/fdw.log"

class CovFdw(ForeignDataWrapper):
    '''
    A foreign data wrapper for accessing an ION coverage data model via erddap
    '''

    def __init__(self, fdw_options, fdw_columns):
        super(CovFdw, self).__init__(fdw_options, fdw_columns)
        self.cov_path = fdw_options["cov_path"]
        self.cov_id = fdw_options["cov_id"]
        self.columns = fdw_columns

        logger = logging.getLogger('fdw_service')
        hdlr = logging.FileHandler(LOG_LOCATION)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr) 
        logger.setLevel(logging.DEBUG)

        self.logger = logger
        self.logger.info("Setting up fdw request...")
        

    def execute(self, quals, req_columns):
        #initiall set it to false        
        param_list = []
        #data must really be in this format
        master_cols = self.columns.keys()

        self.logger.info("req_columns:"+str(req_columns))

        time_available = False
        time_bounds = None

        #self.logger.info("quals:"+str(quals))
        for qual in quals:            
            if (qual.field_name == TIME):
                if time_bounds is not None:
                    time_bounds+= "&"+str(qual.field_name)+str(qual.operator)+str(qual.value)
                else:
                    time_bounds = "&"+str(qual.field_name)+str(qual.operator)+str(qual.value)
                    time_available = True

        #fix the arrows
        time_bounds = time_bounds.replace(">", "%3E")
        time_bounds = time_bounds.replace("<", "%3C")


        #TODO verify requested requirements
        if len(req_columns) == len(master_cols):
            #####SIMPLE---------
            #if the request is the same length as available just set it, else construct it
            param_list = master_cols
             #check that the length requested is the same as the length available
            ret_data = self.getSimpleDataStruct(param_list,time_available,time_bounds)            
            #if there is data
            for row in ret_data:
                yield row   
            #-------------------
        else:
            #####COMPLEX--------
            #get the req columns
            for param in req_columns:
                param_list.append(param)           
               
            self.logger.info("DataFields   Requested:"+str(param_list))
            ret_data = self.getSimpleDataStruct(param_list,time_available,time_bounds)

            for row in ret_data:
                #create new row from data
                new_row = {}
                for col in master_cols:
                    #create empty row
                    new_row[col] = None

                for i in range(0,len(param_list)):
                    #add data in for requested params
                    param = param_list[i]                    
                    self.logger.info("param:"+str(param))
                    self.logger.info("val:"+str(row[i]))
                    new_row[param] = row[i]

                self.logger.info("row:"+str(new_row))
                yield new_row  

            
            #-------------------     

    def getSimpleDataStruct(self,param_list,time_available,time_bounds):
        '''
        used to obtain the data when all fields are requested
        i.e a simple/typical request 
        '''
        self.logger.info("resourceID:",self.cov_id)
        cov_available = False 
        try:

            dataproduct_id,_ = self.request_resource_action('resource_registry', 'find_subjects', **{"object":self.cov_id, "predicate":'hasDataset', "id_only":True})
            if (len(dataproduct_id))> 0:
                dp_id = dataproduct_id[0]
                self.logger.info("data product id from sgs:"+str((dataproduct_id[0])))
                
                #create time bounds if available
                if time_available:
                    time_bounds_str = time_bounds
                else:
                    time_bounds_str = ""

                resource = "data" + dp_id
                #create url
                url = SERVER+resource+".json?"+ ",".join(param_list)+time_bounds_str
                
                #if time is in there add the orderby
                if TIME in param_list:
                    url +="&orderBy(%22time%22)"
                                
                self.logger.info(url)
                r = requests.get(url)
                if r.status_code == 200:
                    #if available                
                    ret_data = r.json()                
                    ret_data = ret_data["table"]["rows"]
                    self.logger.info("got data...")
                    cov_available = True
                elif "Your query produced no matching results" in r.text:
                    #no data
                    self.logger.info("No data for request...")
                else:    
                    #error
                    self.logger.info("Could not get data..."+r.text)
                    #return nothing
        except Exception, e:
                #fail            
                self.logger.error("Failed to get data...:" + str(e))         

        #loads a coverage, everything else returns empty array
        if cov_available:
            return ret_data 
        else:
            return []       


    def request_resource_action(self, service_name, op, **kwargs):  

        url = SGS_URL
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