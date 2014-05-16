ooi-extern
==========

## Using the resync service

### simple test

start a container using something like the following `bin/pycc --rel res/deploy/r2deploy.yml -s test -fc`
when you get to the command line do a `start_mx()`. you can also inlcude the flag to start it during container load.

start the resync server `bin/ipython sync_init.py`

then pass it a query something like `http://localhost:8848/syncharvesters=neptune,ioos&ooi=geonetwork`

## Using the importer service

in order for the coverage model to be loaded and used the [pyon.yml name](https://github.com/ooici/ion-definitions/blob/master/res/config/pyon.yml#L14)  needs to be set to `ion` other wise the data will not be loaded.

## initial setup
cd to the ooi-extern directory and do a `python bootstrap.py`, once complete do a `bin/buildout`.

## Importer Service
This service handles the communication between the DMS and Geoserver. The importer service allows the modification (add,remove) of geoserver data layers from ooi coverages

run `bin/ipython init.py`

the service will tell you which port it is on. you can simply then pass a query to the service eg.

is the service alive
`http://localhost:8844/service=alive&name=ooi&id=ooi`

add a layer
`http://localhost:8844/service=addlayer&name="DATASET_ID"&id="DATASET_ID"`

reset the datastore
`http://localhost:8844/service=resetstore&name=ooi&id=ooi`

### Install Notes

NOTE: postgres needs to be buildout against pyon 2.7.X other wise things will not run correctly you can modify your postgres setup to bypass some of the issues if you are using  `supd` but this requires adding paths to eggs for coverage and everything else.

### Typical use of FDW

i suggest reading information on FDW from the [multicorn page](http://multicorn.org/foreign-data-wrappers) before proceding

* Create the extension
```
CREATE EXTENSION multicorn
```

* create the server using the FDW
``` 
CREATE SERVER cov_srv foreign data wrapper multicorn options (
    wrapper 'covfdw.CovFdw'
);
```

* create the foreign data table with the path to the dataset
```
  drop foreign table covtest;

  create foreign table covtest (
       dataset_id character varying,
       time timestamp,
       cond real,
       temp real,
       lat real,
       lon real,
       "geom" geometry(Point,4326)      
) server cov_srv options (cov_path '/path/to/dataset/44afbd5858c44a8494f171d15e76d0ab',cov_id '44afbd5858c44a8494f171d15e76d0ab');
```

* you can add this to a postgres function as follows
``` sql
CREATE OR REPLACE FUNCTION runCovTest() returns text as $$
  drop foreign table covtest;
  
  create foreign table covtest (
       dataset_id character varying,
       time timestamp,
       cond real,
       temp real,
       lat real,
       lon real,
       "geom" geometry(Point,4326)        
) server cov_srv options (cov_path '/path/to/datasets/44afbd5858c44a8494f171d15e76d0ab',cov_id '44afbd5858c44a8494f171d15e76d0ab');

$$ LANGUAGE SQL ;
```

* Because the srid is fixed geom can be overridden using postgres mk_point, to caluclate the SRID from the lat,lon of a coverage by generating a postgres view as follows.
```
CREATE or replace VIEW covproj as 
SELECT ST_SetSRID(ST_MakePoint(lon, lat),4326) as proj, dataset_id, time, cond, temp from covtest;
```

* notice that the server is called `cov_src`, and the data table is called `cov_test` and the view containing the srid information is called `covproj`. To view the information stored you could simply do:
``` sql
SELECT * [time,cond,temp] from covproj [limit #] [where 'field' = 'condition'];
```

###Install FDW alongside coverage model using ooivm.

before proceding review the following site, particually the "how do we do that?" section:

```
http://multicorn.org/implementing-an-fdw/
```

Create a new user

```
sudo adduser eoitest
sudo passwd eoitest
```

Add eoitest to /etc/sudoers
```
sudo vi /etc/sudoers
```

move to postgres user to create some python functions

```
sudo su - postgres
```

create language

`CREATE LANGUAGE plpythonu;`

create path verification function

```
CREATE or replace FUNCTION checkpath ()
  RETURNS text
AS $$
 import sys
 import os

 print sys.version
 print sys.path 

 return '\n'.join(sys.path)
$$ LANGUAGE plpythonu;

```

test it

```
select checkPath();
```

quit

```
\q
```

go to the eoi user
```
sudo su - eoitest
```

modify default python version

```
vi ~/.bash_profile
```

```
# .bash_profile

# Get the aliases and functions
if [ -f ~/.bashrc ]; then
        . ~/.bashrc
fi

# User specific environment and startup programs

PATH=/opt/python2.7/bin:$PATH
PATH=/opt/python2.7/bin:$PATH
PATH=/home/eoitest/ooi-extern/fdw:$PATH

export PATH
```

as the postgres user do the same as above

switch to the postgres user
```
sudo su - postgres
```

drop existing multicorn items
```
drop extension multicorn cascade;
```

as sudo in eoitest

`easy_install pip` then clone the repo `git clone [url for repo] ooi-extern`. install the coverage fdw by going to the directory `cd /home/eoitest/ooi-extern/fdw` then `sudo /opt/python2.7/bin/python setup.py install`

you should see the following at the end of the build, this shows the egg was build and moved to the correct location. take note that it says py2.7.egg!

```
Installed /opt/python2.7/lib/python2.7/site-packages/covfdw-0.0.1-py2.7.egg
Processing dependencies for covfdw==0.0.1
Finished processing dependencies for covfdw==0.0.1
```

change to postgres user then do ``` psql ```

verify that the egg is on the package list i.e (/opt/python2.7/lib/python2.7/site-packages/covfdw-0.0.1-py2.7.egg)

```
select checkPath();
```

quit and login to eoitest user, and go to ooi-extern directory

`\q`

`sudo su - eoitest`

`cd ~/ooi-extern`

create virtual env to hold all the python stuff
`mkvirtualenv --no-site-packages eoipg`

then do the following 
```
pip install numpy==1.7.1
pip install -U setuptools==0.8
pip install --upgrade setuptools
```

edit the profile
```
vi ~/.bash_profile
```

add `workon eoipg`


get the submodules and initalize them using the virtual machine python
```
git submodule update --init
```

```cd extern/gsconfig```

use virtual machine python

`sudo ~/.virtualenvs/eoipg/bin/python setup.py develop`

### Coverage Model

build out the coverage model.
`cd ../coverage-model`

`git submodule update --init`

`sudo ~/.virtualenvs/eoipg/bin/python bootstrap.py -v 2.2.0`


build out the coverage model `bin/buildout`, incase of permissions issues do this: `sudo chown eoitest:eoitest coverage-model`

* if you get an error for psycopg2 do the following `pip install psycopg2==2.5.1` then `bin/buildout`

build out the interfaces `bin/generate_interfaces` you should get the following `generate_interfaces: Completed with exit code: 0`


### Pyon
```
cd ../pyon
git submodule update --init
sudo ~/.virtualenvs/eoipg/bin/python bootstrap.py -v 2.2.0
```
incase of permissions issues `sudo chown eoitest:eoitest pyon`
`bin/buildout`
`bin/generate_interfaces`

coverage model dependancy on pyon is here
```
https://github.com/ooici/coverage-model/blob/master/coverage_model/utils.py
```

the site packages for postgres should be located in `/opt/python2.7/lib/python2.7/site-packages`

sort out python pathing issues, i.e the python path in psql
for notes see `http://www.postgresql.org/docs/9.2/static/plpython-envar.html`

the PYTHONPATH needs to be set in the following file `/etc/profile.d/postgresql.sh` with all the eggs in the coverage model.

cd to dir and make backup
`cd /etc/profile.d/`
`sudo cp postgresql.sh postgresql.sh.bk`

in ~/ooi-extern of eoitest do
`find /home/eoitest/ooi-extern/extern/coverage-model/eggs -name *.egg > eoieggs.txt`

then create the new file to contain the python path information
`python path_tool.py`

as main user not POSTGRES or EOITEST

```
sudo bash -c 'cat /home/eoitest/ooi-extern/python_path.txt >> /etc/profile.d/postgresql.sh'
```

set python in postgressql.sh
```
export PYTHON=/opt/python2.7/bin/python:$PYTHON
```

install the following (maybe dont do this) instead change permissions (chmod 755 user dir eoitest)

```
sudo /opt/python2.7/bin/easy_install pip
sudo /opt/python2.7/bin/pip install numexpr
sudo /opt/python2.7/bin/pip install simplejson
```

make sure numpy is installed
```
sudo /opt/python2.7/bin/pip install numpy
sudo /opt/python2.7/bin/pip install psycopg2
```
if requirement is satisfied `Requirement already satisfied`

install psycopg2 and regular user not eoitest or postgres
`pip install psycopg2`

make sure numpy and psycopg2 are on the `select checkPath();` list, if it is not add it
i.e 
```
/opt/python2.7/lib/python2.7/site-packages/numpy-1.8.1-py2.7.egg-info
/opt/python2.7/lib/python2.7/site-packages/psycopg2-2.5.2-py2.7.egg-info
```

restart the services by doing a `sudo /etc/init.d/postgresql-9.3 stop` then ps -ef | grep psql or postgres to see if it stopped running then `sudo /etc/init.d/postgresql-9.3 start`. check that the path has been updated using...

```
sudo su - postgres
psql
select checkPath();
```

create and run the imports that are used by the covfdw to verify they will work

```
CREATE or replace FUNCTION test ()
  RETURNS text
AS $$
 import sys
 import math
 import numpy as np
 import numpy
 import string
 import time
 from multicorn import ColumnDefinition
 from multicorn import ForeignDataWrapper
 from multicorn import Qual
 from multicorn.compat import unicode_
 from multicorn.utils import log_to_postgres,WARNING,ERROR

 from numpy.random import random
 import numexpr as ne

 import simplejson
 from gevent import server
 from gevent.monkey import patch_all; patch_all()

 import gevent

 import random
 from random import randrange
 import os 
 import datetime

 from coverage_model import SimplexCoverage, AbstractCoverage,QuantityType, ArrayType, ConstantType, CategoryType

 return '\n'.join(sys.path)
$$ LANGUAGE plpythonu;
```

verify it works by doing a `select test();` in postgres

if not errors occur do the following
```
CREATE SERVER cov_srv foreign data wrapper multicorn options (
    wrapper 'covfdw.CovFdw'
);
```

## EOI VM Software Installation
### GeoServer
Get latest GeoServer WAR file from GeoNode here:
`http://build.geonode.org/geoserver/latest/geoserver.war`
and place in the following directory:
`/usr/share/apache-tomcat-7.0.53/webapps/`

### GeoNetwork
Get latest GeoNetwork WAR file starting from this general location (dynamic link):
`http://geonetwork-opensource.org/downloads.html`

and place in the following directory:
`/usr/share/apache-tomcat-7.0.53/webapps/`

Change default database from H2 to PostgreSQL
`cd $CATALINA_HOME\lib`
`sudo wget http://jdbc.postgresql.org/download/postgresql-9.3-1101.jdbc41.jar`
`sudo vi  /usr/share/apache-tomcat-7.0.53/conf/tomcat-users.xml`

```
<tomcat-users>
  <role rolename="tomcat"/>
  <role rolename="manager-gui"/>
  <role rolename="manager-script"/>
  <role rolename="manager-jmx"/>
  <role rolename="manager-status"/>
  <user username="admin" password="*****" roles="tomcat,role1,manager-gui,manager-status"/>
</tomcat-users>
```

Enable the PostgreSQL database in:
`/usr/share/apache-tomcat-7.0.53/webapps/geonetwork/WEB-INF/config.xml`
as follows: and ensure the default H2 resource is set to "false" (only one resource enabled)
```
                <!-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -->
                <!-- postgresql -->
                <!-- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -->

                <resource enabled="true">
                        <name>main-db</name>
                        <provider>jeeves.resources.dbms.ApacheDBCPool</provider>
                        <config>
                                <user>ooici</user>
                                <password>*****</password>
                                <!-- we use org.postgis.DriverWrapper in place of
                                org.postgresql.Driver to support both postgresql and postgis -->
                                <driver>org.postgis.DriverWrapper</driver>
                                <!--
                                        jdbc:postgresql:database
                                        jdbc:postgresql://host/database
                                        jdbc:postgresql://host:port/database

                                        or if you are using postgis and want the spatial index loaded
                                        into postgis

                                        jdbc:postgresql_postGIS://host:port/database

                                -->
                                <url>jdbc:postgresql_postGIS://localhost:5432/geonetwork</url>
                                <poolSize>10</poolSize>
                                <validationQuery>SELECT 1</validationQuery>
                        </config>
                </resource>
```
Ensure the root and user have the following in their respective .bash_profile:
```
# User specific environment and startup programs
JAVA_HOME=/usr/java/jdk1.7.0_55
export JAVA_HOME

PATH=/opt/python2.7/bin:$PATH:$HOME/bin:$JAVA_HOME/bin
PATH=/home/eoitest/ooi-extern/fdw:$PATH

CATALINA_HOME=/usr/share/apache-tomcat-7.0.53

export PATH
export CATALINA_HOME
```

Ensure that /etc/init.d/tomcat has the following content:
```
#!/bin/bash
# description: Tomcat Start Stop Restart
# processname: tomcat
# chkconfig: 234 20 80
JAVA_HOME=/usr/java/jdk1.7.0_55
export JAVA_HOME
PATH=$JAVA_HOME/bin:$PATH
export PATH
CATALINA_HOME=/usr/share/apache-tomcat-7.0.53
JAVA_OPTS="-Xms2048m -Xmx6000m -XX:MaxPermSize=2048m"
export JAVA_OPTS

case $1 in
start)
sh $CATALINA_HOME/bin/startup.sh
;;
stop)
sh $CATALINA_HOME/bin/shutdown.sh
;;
restart)
sh $CATALINA_HOME/bin/shutdown.sh
sh $CATALINA_HOME/bin/startup.sh
;;
esac
exit 0
```
