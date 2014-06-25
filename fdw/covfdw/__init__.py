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
import simplejson
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

SERVER = "http://erddap-test.oceanobservatories.org:8080/erddap/tabledap/"

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
        cov_available = False 
        param_list = []
        #data must really be in this format
        master_cols = self.columns.keys()

        for qual in quals:
                if (qual.field_name == TIME):
                    log_to_postgres(
                        "qualField:"+ str(qual.field_name) 
                        + " qualOperator:" + str(qual.operator) 
                        + " qualValue:" +str(qual.value), WARNING)


        for param in master_cols:
            if param == "lat":
                param = "latitude"
            elif param == "lon":
                param = "longitude"
            
            param_list.append(param)    

        self.logger.info("DataFields Requested:"+str(param_list)+"\n"+"master:"+ str(master_cols))

        #check that the length requested is the same as the length available
        if len(req_columns) == len(master_cols):
            ret_data = self.getSimpleDataStruct(param_list)
            for row in ret_data:
                yield row   
        else:
            #length is different               
            self.logger.info("DataFields Requested dont match those availabe")


    def getSimpleDataStruct(self,param_list):
        '''
        used to obtain the data when all fields are requested
        i.e a simple/typical request 
        '''
        self.logger.info("resourceID:",self.cov_id)

        try:
            self.logger.info("getting data from errdap")
            time_bounds = "&time%3E=2014-02-22T21:51:42.615Z&time%3C=2014-02-22T22:11:46.501Z"
            resource = "data"+"a990236fb3184d6bbefec7cc267ce307"
            url = SERVER+resource+".json?"+ ",".join(param_list)+time_bounds
            
            if "time" in param_list:
                url +="&orderBy(%22time%22)"
                            
            self.logger.info(url)
            r = requests.get(url)
            if r.status_code == 200:                
                ret_data = r.json()                
                ret_data = ret_data["table"]["rows"]
                self.logger.info("got data...")
                cov_available = True
            else:    
                self.logger.info("Could not get data..."+r.text)
        except Exception, e:            
                self.logger.error("Failed to get data...:" + str(e))            
        
        #loads a coverage
        if cov_available:
            return ret_data           