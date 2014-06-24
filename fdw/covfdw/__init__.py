"""
An ION Coverage Foreign Data Wrapper
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
import numexpr as ne

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
    """A foreign data wrapper for accessing an ION coverage data model.
    Valid options:
    - time, inside the coverage model, shoulud always be seconds since 1900-01-01
    - add 2208988800, number of seconds between 1900-01-01 and 1970-01-01
    """

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

        for param in req_columns:
            if param == "lat":
                param = "latitude"
            elif param == "lon":
                param = "longitude"
            
            param_list.append(param)    

        self.logger.info("DataFields Requested:"+str(param_list))

        try:
            self.logger.info("getting data from errdap")
            time_bounds = "&time%3E=2014-02-22T21:51:42.615Z&time%3C=2014-02-28T18:11:46.501Z"
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
                self.logger.info("could not get data..."+r.text)
        except Exception, e:            
                self.logger.error("Failed to get data...:" + str(e))

        for qual in quals:
            if (qual.field_name == TIME):
                log_to_postgres(
                    "qualField:"+ str(qual.field_name) 
                    + " qualOperator:" + str(qual.operator) 
                    + " qualValue:" +str(qual.value), WARNING)
        
        #loads a coverage
        if cov_available:   
            return ret_data
            
    def append_mock_data_based_on_type(self,data_type,data):
        if (data_type.startswith("timestamp")):
            data.append(self.param_mock_time_data)
        elif(data_type.startswith("real")):
            data.append(self.param_mock_data)    
        else:
             data.append(self.param_mock_data)    
        return data            


    def generate_mock_real_data(self,data_length):
        start = time.time()
        self.param_mock_data = np.repeat(0, [data_length], axis=0)
        elapsedGen = (time.time() - start)
        log_to_postgres("Time to complete MockData:"+str(elapsedGen), WARNING)   

    #generate mock time data
    def generate_mock_time_data(self,data_length):
        #generate array of legnth
        #time is seconds since 1970-01-01 (if its a float)
        start = time.time()
        self.param_mock_time_data = np.array([1+i for i in xrange(data_length)])
        elapsedGen = (time.time() - start)
        log_to_postgres("Time to complete MockTimeData:"+str(elapsedGen), WARNING)          

    #convert date time object to string
    def get_times(self,param_time):
        #date time float is seconds since 1970-01-01
        #formats the datetime string as  
        s = [datetime.datetime.strftime(datetime.datetime.utcfromtimestamp(e*1000),"%Y-%m-%d %H:%M:%S") for e in param_time]
        return s  