ooi-extern
==========

## Using the service

in order for the coverage model to be loaded and used the [pyon.yml name](https://github.com/ooici/ion-definitions/blob/master/res/config/pyon.yml#L14)  needs to be set to ```ion``` other wise the data will not be loaded.

importer service allows the modification (add,remove) of geoserver data layers from ooi coverages

run ```bin/ipython```

enter ```import importer_service```

enter ```importerService.ResourceImporter()```

the service will tell you which port it is on. you can simply then pass a query to the service eg.

is the service alive
http://localhost:8844/service=alive&name=ooi&id=ooi

add a layer
http://localhost:8844/service=addlayer&name="DATASET_ID"&id="DATASET_ID"

reset the datastore
http://localhost:8844/service=resetstore&name=ooi&id=ooi

## macosx

install postgres to a virtual env named "postgres"
pull down this repo and run ```python bootstrap.py``` and ```bin/buildout``` to develope the eggs needed.

```git submodule update --init```

### Install

for the simple install see below, for a more complex overview please see the following link. NOTE: postgres needs to be buildout against pyon 2.7.X other wise things will not run correctly you can modify your postgres setup to bypass some of the issues i.e in ```supd`` but this requires adding paths to eggs for coverage and everything else etc.

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
) server cov_srv options (k '1',cov_path '/path/to/dataset/44afbd5858c44a8494f171d15e76d0ab',cov_id '44afbd5858c44a8494f171d15e76d0ab');
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
) server cov_srv options (k '1',cov_path '/path/to/datasets/44afbd5858c44a8494f171d15e76d0ab',cov_id '44afbd5858c44a8494f171d15e76d0ab');

$$ LANGUAGE SQL ;
```

* because the srid is fixed geom can be overridden using postgres mk_point, to caluclate the SRID from the lat,lon of a coverage by generating a postgres view as follows.
```
CREATE or replace VIEW covproj as 
SELECT ST_SetSRID(ST_MakePoint(lon, lat),4326) as proj, dataset_id, time, cond, temp from covtest;
```

* notice that the server is called ```cov_src```, and the data table is called ```cov_test``` and the view containing the srid information is called ```covproj```. To view the information stored you could simply do:
``` sql
SELECT * [time,cond,temp] from covproj [limit #] [where 'field' = 'condition'];
```




