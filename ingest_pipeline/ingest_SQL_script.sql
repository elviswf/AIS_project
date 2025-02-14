CREATE EXTENSION postgis;

-- Create table
CREATE TABLE IF NOT EXISTS cargo_ship_position
(
    uid text,
    time timestamp,
    lat numeric,
    lon numeric
)

-- add primary key
alter table cargo_ship_position
add column id serial primary key;

-- add geom column
ALTER TABLE cargo_ship_position
add column geom geometry(Point, 4326);
-- populate with geom from lat and lon
UPDATE cargo_ship_position SET geom = ST_SetSRID(
	ST_MakePoint(lon, lat), 4326);

CREATE INDEX ship_position_uid_idx on cargo_ship_position (uid);
CREATE INDEX ship_position_geom_idx ON cargo_ship_position USING GIST (geom);

--ship trips
CREATE TABLE ship_trips AS
SELECT uid,
		position_count,
		line,
		ST_Length(geography(line))/1000 AS line_length_km,
		first_date,
		last_date,
		last_date - first_date as time_diff
FROM (
 SELECT pos.uid,
 COUNT (pos.geom) as position_count,
 ST_MakeLine(pos.geom ORDER BY pos.time) AS line,
 MIN (pos.time) as first_date,
 MAX (pos.time) as last_date
 FROM cargo_ship_position as pos
 GROUP BY pos.uid) AS foo;

 --this works and creates a new table.  5/9/2019 created ship_ports
 --i used geom to calc distance instead of geog.  the knn should be fine but dist
 -- is wrong.
 --reworked 10 may.  reran, but still takes about 17 hours.
 --need to make a sample of this still in prod
 --need to add indicies in prod still
 create table ship_ports as
 with knn as (select posit.id, posit.uid, posit.time, posit.geom as ship_posit,
 	wpi.index_no as nearest_site_id,
 	wpi.geog as port_geog
 	from cargo_ship_position as posit
 	cross join lateral
 	(select wpi.index_no,
 	 wpi.geog
 	 from wpi
 	 order by
 	wpi.geom <-> posit.geom limit 1)
 	as wpi)
 select knn.id, knn.uid, knn.time, knn.nearest_site_id,
 (ST_Distance(knn.port_geog, knn.ship_posit::geography)/1000) AS nearest_site_dist_km
 from knn
 join ship_position_1000 as posit
 on knn.id = posit.id

--returns all ports with the count of positions at that port within
--specified distance (currently 5km)
--need to make a sample of this still in prod
create table ports_5k_positions as
select
	wpi.port_name,
	ship_ports.nearest_site_id,
	count(ship_ports.id),
	wpi.geom
from ship_ports as ship_ports, wpi
where ship_ports.nearest_site_id=wpi.index_no
and ship_ports.nearest_site_dist_km < 5
group by (ship_ports.nearest_site_id, wpi.port_name, wpi.geom)
order by count

