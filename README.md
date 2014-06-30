# ooi-extern (ooi external services), EOI-Services

OOI Extern project encompasses the majority of the items required for the EOI services of [OOI](https://github.com/ooici/coi-services)

## Overview of Services

There are a number of services that make up the EOI service stack, the majority of which are located in this project. The list below outlines each of them and a quick overview.

* Importer service (has an [init](https://github.com/ooici/ooi-extern/blob/master/init.py))
    * is a WSGI service   
* Resync service (has an [init](https://github.com/ooici/ooi-extern/blob/master/sync_init.py))
    * is a WSGI service   
* Neptune SOS service (Neptune SOS service handler/middle man service)
    * is a WSGI service      
* Coverage FDW (foreign data wrapper), (has a [setup](https://github.com/ooici/ooi-extern/blob/master/fdw/setup.py))
    * postgres extension (requires multicorn, and postgres using python 2.7.x (not 2.6))   

## Install

* cd to the ooi-extern directory and do a `python bootstrap.py`, once complete, do a `bin/buildout`.

## Resync service

The resync service creates resources inside the resources registry for harvester metadata records.

### Example

* start an OOI container using something like the following `bin/pycc --rel res/deploy/r2deploy.yml -s test -fc`
* when the loading finishes and you get to the command line do a `start_mx()` (you can also inlcude the flag to start it during container load)
* start the resync server `bin/ipython sync_init.py`
* pass it a query something like `http://localhost:8848/syncharvesters=neptune,ioos&ooi=geonetwork`
* The above query tells the resync service to sync the defined harvesters

## Importer service

The importer service is used by [coi-services specifically table loader](https://github.com/ooici/coi-services/blob/master/ion/services/eoi/table_loader.py) to generate externally available endpoints via geoserver. These endpoints are generate from the dataset management service and every public dataset processed. The importer service allows the modification (add,remove) of geoserver data layers from ooi coverages

The importer service is also used to handler some aspects of the metadata harvesters used in geonetwork

### Example

* run `bin/ipython init.py`

* is the service alive `http://localhost:8844/service=alive&name=ooi&id=ooi`

* add a layer `http://localhost:8844/service=addlayer&name="DATASET_ID"&id="DATASET_ID"`

* `http://localhost:8844/service=resetstore&name=ooi&id=ooi`

### Install Notes

NOTE: postgres needs to be buildout against python 2.7.X other wise things will not run correctly you can modify your postgres setup to bypass some of the issues if you are using  `supd` but this requires adding paths to eggs.

## Typical use of FDW

I suggest reading information on FDW from the [multicorn page](http://multicorn.org/foreign-data-wrappers) before proceding. The FDW needs to be created manually in the postgres instance, the FDT's are created automatically in the coi-services table-loader.py.

Manually create the extension
* Create the extension
```
CREATE EXTENSION multicorn
```

Manually create the server
* create the server using the FDW
``` 
CREATE SERVER cov_srv foreign data wrapper multicorn options (
    wrapper 'covfdw.CovFdw'
);
```

Below is a short example on the creation of a FDT, once the extension and server are created

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

* the view is created automatially. Because the srid is fixed geom can be overridden using postgres mk_point, to caluclate the SRID from the lat,lon of a coverage by generating a postgres view as follows.
```
CREATE or replace VIEW covproj as 
SELECT ST_SetSRID(ST_MakePoint(lon, lat),4326) as proj, dataset_id, time, cond, temp from covtest;
```

* notice that the server is called `cov_src`, and the data table is called `cov_test` and the view containing the srid information is called `covproj`. 
To view the information stored you could simply do:
``` sql
SELECT * [time,cond,temp] from covproj [limit #] [where 'field' = 'condition'];
```

## Install the FDW 

The foreign data wrapper (FDW) allows the communication of data via postgres. To install the EOI FDW there is a [`setup.py`]( https://github.com/ooici/ooi-extern/blob/master/fdw/setup.py) that does all the hard work. This setup file installs the egg to the `site-packages` directory, so be sure you are in the correct `virt env` when doing it.

## Install EOI Services

### Short Version

At present the FDW/FDT does not use the coverage-model/pyon, therefore the dependancy list is only `json` and `requests`. These dependancies are required for the connection and parsing of the [erddap json data](https://github.com/ooici/ooi-extern/blob/master/fdw/covfdw/__init__.py#L118-L129). As long as these dependancies are available in the postgres instance the FDW/FDT should work fine.

### Long version

Before proceding review the following site, particually the "how do we do that?" section:

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
pip install requests
pip install simplejson
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

the site packages for postgres should be located in `/opt/python2.7/lib/python2.7/site-packages`

sort out python pathing issues, i.e the python path in psql
for notes see `http://www.postgresql.org/docs/9.2/static/plpython-envar.html`

the PYTHONPATH needs to be set in the following file `/etc/profile.d/postgresql.sh`

cd to dir and make backup
`cd /etc/profile.d/`
`sudo cp postgresql.sh postgresql.sh.bk`

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
```
if requirement is satisfied `Requirement already satisfied`

make sure numpy is on the `select checkPath();` list, if it is not add it
i.e 
```
/opt/python2.7/lib/python2.7/site-packages/numpy-1.8.1-py2.7.egg-info
```

restart the services by doing a `sudo /etc/init.d/postgresql-9.3 stop` then `ps -ef | grep psql` or postgres to see if it stopped running then `sudo /etc/init.d/postgresql-9.3 start`. check that the path has been updated using...

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
 import numpy as np
 from multicorn import ColumnDefinition
 from multicorn import ForeignDataWrapper
 from multicorn import Qual
 from multicorn.utils import log_to_postgres,WARNING,ERROR

 import simplejson
 import requests

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

## Deployment
### GeoNetwork
After system launch, all of the harvesters can be run by 'browsing' to the following url using curl or a web browser:
```
http://localhost:8844/service=runharvester&hfilter=all
```
### Supervisord
If desired, place the following supervisord configuration files in /etc/supervisord.d/ for the EOI services:
Replace eoitest with the appropriate user and check paths.

eoi_importer_service.conf
```
[program:eoi_importer_service]
directory=/home/eoitest/ooi-extern/
command=/home/eoitest/ooi-extern/bin/ipython init.py
user=eoitest
autostart=true
autorestart=true
redirect_stderr=True
```
eoi_resync_service.conf
```
[program:eoi_resync_service]
directory=/home/eoitest/ooi-extern/
command=/home/eoitest/ooi-extern/bin/ipython sync_init.py
user=eoitest
autostart=true
autorestart=true
redirect_stderr=True
```
eoi_sos_service.conf
```
[program:eoi_sos_service]
directory=/home/eoitest/ooi-extern/
command=/home/eoitest/ooi-extern/bin/ipython geonetwork/init_sos_handler.py
user=eoitest
autostart=true
autorestart=true
redirect_stderr=True
```
