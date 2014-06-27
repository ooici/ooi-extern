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
        hdlr = logging.FileHandler('/Users/rpsdev/log/fdw.log')
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

        time_bounds = False
        for qual in quals:
                if (qual.field_name == TIME):
                    time_bounds = True
                    log_to_postgres(
                        "qualField:"+ str(qual.field_name) 
                        + " qualOperator:" + str(qual.operator) 
                        + " qualValue:" +str(qual.value), WARNING)


        self.logger.info("quals:"+str(quals))

        for param in master_cols:
            #if param == "lat":
            #    param = "latitude"
            #elif param == "lon":
            #    param = "longitude"
            
            param_list.append(param)           

        #check that the length requested is the same as the length available
        if len(param_list) == len(master_cols):
            ret_data = self.getSimpleDataStruct(param_list,time_bounds)
            
            #if there is data
            for row in ret_data:
                yield row   
        else:
            #length is different               
            self.logger.info("DataFields Requested dont match those availabe")
            self.logger.info("DataFields   Requested:"+str(param_list))
            self.logger.info("masterFields Requested:"+ str(master_cols))                        
            self.logger.info(str(len(param_list))+" vs " + str(len(master_cols)))


    def getSimpleDataStruct(self,param_list,time_bounds):
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
                if time_bounds:
                    time_bounds_str = "&time%3E=2014-02-22T21:51:42.615Z&time%3C=2014-02-22T22:11:46.501Z"
                else:
                    time_bounds_str = ""

                resource = "data" + dp_id
                #create url
                url = SERVER+resource+".json?"+ ",".join(param_list)+time_bounds_str
                
                #if time is in there add the orderby
                if "time" in param_list:
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
                    self.logger.info("not data for request...")
                    return None
                else:    
                    #error
                    self.logger.info("Could not get data..."+r.text)
                    return None
        except Exception, e:
                #fail            
                self.logger.error("Failed to get data...:" + str(e))            

        
        #loads a coverage
        if cov_available:
            return ret_data 
        else:
            return None       





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