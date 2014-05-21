CREATE TABLE public.metadataregistry (
  id            serial NOT NULL PRIMARY KEY,
  gnuuid        varchar(250) NOT NULL,
  rruuid        varchar(250) NOT NULL,
  registerdate  varchar(30) NOT NULL
) WITH (
    OIDS = FALSE
  );

ALTER TABLE public.metadataregistry
  OWNER TO ooici;

COMMENT ON COLUMN public.metadataregistry.gnuuid
  IS 'GeoNetwork UUID';

COMMENT ON COLUMN public.metadataregistry.rruuid
  IS 'OOI Resource Registry UUID';

COMMENT ON COLUMN public.metadataregistry.registerdate
  IS 'The date the associated metadata was last syncronized with the OOI RR';