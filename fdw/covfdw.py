"""
An ION Coverage Foreign Data Wrapper
"""

__author__ = 'abird'

import sys
import math
import numpy as np
import numpy
import string
import time
from numpy.random import random
import numexpr as ne

import simplejson
from gevent import server
from gevent.monkey import patch_all; patch_all()
from pyon.util.breakpoint import breakpoint
from pyon.util.file_sys import FileSystem, FS

import gevent

from multicorn import ColumnDefinition
from multicorn import ForeignDataWrapper
from multicorn import Qual
from multicorn.compat import unicode_
from .utils import log_to_postgres
from logging import WARNING,ERROR

from coverage_model.search.coverage_search import CoverageSearch, CoverageSearchResults, SearchCoverage
from coverage_model.search.search_parameter import ParamValue, ParamValueRange, SearchCriteria
from coverage_model.search.search_constants import IndexedParameters

from coverage_model import SimplexCoverage, AbstractCoverage,QuantityType, ArrayType, ConstantType, CategoryType

import random
from random import randrange
import os 
import datetime

TIME = 'time'

#size of mock data
cov_fail_data_size = 10**2
#used for by passing coverage issues and generating mock data
debug = False

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

    def execute(self, quals, req_columns):
        #WARNING:  qualField:time qualOperator:>= qualValue:2011-02-11 00:00:00
        #WARNING:  qualField:time qualOperator:<= qualValue:2011-02-12 23:59:59
        log_to_postgres("LOADING Coverage At Path: "+self.cov_path, WARNING)
        log_to_postgres("LOADING Coverage ID: "+self.cov_id, WARNING)
        os.chdir('/Users/rpsdev/externalization')
        log_to_postgres("dir: "+os.getcwd()+" \n")

        #initiall set it to false
        cov_available = False 
        try:
            log_to_postgres("LOADING Coverage", WARNING)
            cov = AbstractCoverage.load(self.cov_path)
            cov_available = True 
            #log_to_postgres("Cov Type:"+type(cov))
        except Exception, e:
            if debug:
                log_to_postgres("failed to load coverage, processing mock data...:" + str(e),WARNING)
            else:     
                log_to_postgres("Failed to load coverage...:" + str(e),ERROR)

        for qual in quals:
            if (qual.field_name == TIME):
                log_to_postgres(
                    "qualField:"+ str(qual.field_name) 
                    + " qualOperator:" + str(qual.operator) 
                    + " qualValue:" +str(qual.value), WARNING)
        
        log_to_postgres("DataFields Requested:"+str(req_columns)+"\n", WARNING)
        #loads a coverage
        if cov_available:
            #log_to_postgres("Coverage PARAMS: "+str(cov.list_parameters())+"\n", WARNING)
            log_to_postgres("TableFields:"+str(self.columns)+"\n", WARNING)
            #time param
            param_time = cov.get_parameter_values(TIME)
            #mock data
            self.generate_mock_real_data(len(param_time))
            self.generate_mock_time_data(len(param_time))
        #if the coverage is not available and debug is set
        else:
            #mock data
            log_to_postgres("addiong mock data as coverage not availabe:"+str(cov_fail_data_size), WARNING)
            self.generate_mock_real_data(cov_fail_data_size)
            self.generate_mock_time_data(cov_fail_data_size)
            param_time = self.param_mock_time_data
            cov_available = True   
            
        if cov_available:    
            #data object
            start = time.time()
            
            data = []
            #actual loop
            for param_item in self.columns:
                data_type = self.columns[param_item].type_name
                col_name = self.columns[param_item].column_name
                log_to_postgres(col_name+" Field: "+param_item+" \t data_type: "+data_type, WARNING)
                if col_name in req_columns:
                    #if the field is time add it to the return block
                    if (param_item == TIME):
                        param_from_cov = self.get_times(param_time)
                        data.append(param_from_cov)

                    elif (col_name.find(TIME)>=0):    
                        data = self.append_mock_data_based_on_type(data_type,data)
                    else:
                        try:
                            param_from_cov = cov.get_parameter_values(col_name)
                            data.append(param_from_cov)
                            pass
                        except Exception, e:
                            data = self.append_mock_data_based_on_type(data_type,data)
                            pass

                else:                
                    data = self.append_mock_data_based_on_type(data_type,data)

            #create np array to return
            dataarray = np.array(data)
            return dataarray.transpose()  
            
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