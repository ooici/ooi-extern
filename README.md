ooi-extern
==========

## Using the service

importer service allows the modification (add,remove) of geoserver data layers from ooi coverages

run ```bin/ipython```

enter ```import importerService```

enter ```importerService.startup()```

the service will tell you which port it is on. you can simply then pass a query to the service eg.

http://localhost:8844/service=addlayer&name="DATASET_ID"&id="DATASET_ID"
http://localhost:8844/service=resetstore&name=ooi&id=ooi

## macosx

install postgres to a virtual env named "postgres"
pull down this repo and run bootstrap.py and bin/buildout to develope the eggs needed.

git submodule update --init

multicorn

virtenv

### 


### postgres data store

../geonode/geoserver/data/workspaces/geonode

kinda looks like this

```
<dataStore>
  <id>DataStoreInfoImpl-1557c66f:143d5325248:-7ffe</id>
  <name>asd</name>
  <description>asd</description>
  <type>PostGIS</type>
  <enabled>true</enabled>
  <workspace>
    <id>WorkspaceInfoImpl-78ff667e:12476299803:-7ffd</id>
  </workspace>
  <connectionParameters>
    <entry key="port">5432</entry>
    <entry key="Connection timeout">20</entry>
    <entry key="dbtype">postgis</entry>
    <entry key="host">localhost</entry>
    <entry key="validate connections">true</entry>
    <entry key="encode functions">false</entry>
    <entry key="max connections">10</entry>
    <entry key="database">postgres</entry>
    <entry key="namespace">http://www.geonode.org/</entry>
    <entry key="schema">public</entry>
    <entry key="Loose bbox">true</entry>
    <entry key="Expose primary keys">false</entry>
    <entry key="Session startup SQL">select runCovTest();</entry>
    <entry key="fetch size">1000</entry>
    <entry key="Max open prepared statements">50</entry>
    <entry key="preparedStatements">false</entry>
    <entry key="Estimated extends">true</entry>
    <entry key="user">rpsdev</entry>
    <entry key="min connections">1</entry>
  </connectionParameters>
  <__default>false</__default>
</dataStore>
```

## centos 6.3 install (tested as a VM)

## create virtual env

### install python 2.7.3 from source to venv

### install postgres from source using python 2.7.3 to venv

### install additional postgis libs

### pull down ooi exten git repo


## setting up coverage data tables

* Create the extension
```
CREATE EXTENSION multicorn
```

* create the server using the FDW
``` 
CREATE SERVER cov_srv foreign data wrapper multicorn options (
    wrapper 'multicorn.covfdw.CovFdw'
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
) server cov_srv options (k '1',cov_path '/path/to/dataset/44afbd5858c44a8494f171d15e76d0ab');
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
) server cov_srv options (k '1',cov_path '/path/to/datasets/44afbd5858c44a8494f171d15e76d0ab');

$$ LANGUAGE SQL ;
```

* because the srid is fixed geom can be overridden using postgres mk_point, to caluclate the SRID from the lat,lon of a coverage by generating a postgres view as follows.
```
CREATE or replace VIEW covproj as 
SELECT ST_SetSRID(ST_MakePoint(lon, lat),4326) as proj, dataset_id, time, cond, temp from covtest;
```

* notice that the server is called cov_src, and the data table is called cov_test and the projection is called covproj.



