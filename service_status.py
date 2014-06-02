#!/usr/bin/env python
 
__author__ = 'Jim Case'
 
from os.path import exists
import requests
import time
import yaml
 
 
class ServiceStatus(object):
    """
    Checks predefined WSGI service endpoint(s) are alive and pass self-tests
    """
 
    def __init__(self):
        self.services = None
        try:
            if exists("services_local.yml"):
                stream = open("services_local.yml")
                self.services = yaml.load(stream)
            elif exists("services.yml"):
                stream = open("services.yml")
                self.services = yaml.load(stream)
            else:
                raise IOError('No services.yml or services_local.yml file exists!')
        except IOError, err:
            print err
 
    def check_once(self):
        """
        Checks all services once
        :return: bool, dict
        """
        health_status = {}
 
        if len(self.services) == 0:
            raise ValueError('No services to process! Check services.yml file.')
 
        for service in self.services:
            try:
                r = requests.post(self.services[service])
                if r.status_code == 200:
                    health_status[service] = True
                else:
                    health_status[service] = False
            except requests.ConnectionError:
                health_status[service] = False
 
        if False in health_status.values():
            return False, health_status
        else:
            return True, health_status
 
    def check_continuous(self, interval):
        """
        Checks all services every n minutes until killed
        :return: None
        """
        while True:
            r, s = self.check_once()
            print "All services passed: ", r
            for status in s:
                print status, s[status]
            time.sleep(interval)