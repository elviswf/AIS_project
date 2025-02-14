#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May 15 07:49:08 2020

@author: patrickmaus
"""

import gsta
import db_config

import pandas as pd
import numpy as np
import datetime
from multiprocessing import Pool
import os
from sklearn.neighbors import BallTree

cores = os.cpu_count()
workers = cores - 1
print(f'This machine has {cores} cores.  Will use {workers} for multiprocessing.')


# set tables for processing
source_table = 'ship_sample'
target_table = 'nearest_sample'
engine = gsta.connect_engine(db_config.colone_cargo_params)
#%% get the sits as a df from the database
sites = gsta.get_sites(engine)
engine.dispose()

# build the BallTree using the ports as the candidates
candidates = np.radians(sites.loc[:, ['lat', 'lon']].values)
ball_tree = BallTree(candidates, leaf_size=40, metric='haversine')

def calc_nn(uid, tree=ball_tree):
    print('Working on uid:', uid[0])
    iteration_start = datetime.datetime.now()
    loc_engine = gsta.connect_engine(db_config.colone_cargo_params, print_verbose=False)
    read_sql = f"""SELECT id, lat, lon
                FROM {source_table}
                where uid= '{uid[0]}';"""
    df = pd.read_sql(sql=read_sql, con=loc_engine)
    loc_engine.dispose()
    # Now we are going to use sklearn's BallTree to find the nearest neighbor of
    # each position for the nearest port.  The resulting port_id and dist will be
    # pushed back to the db with the id, uid, and time to be used in the network
    # building phase of analysis.  This takes up more memory, but means we have
    # fewer joins.  Add an index on uid though before running network building.
    # transform to radians
    points_of_int = np.radians(df.loc[:, ['lat', 'lon']].values)
    # query the tree
    dist, ind = tree.query(points_of_int, k=1, dualtree=True)
    # make the data list to pass to the sql query
    data = np.column_stack((np.round(((dist.reshape(1, -1)[0]) * 6371.0088), decimals=3),
                            sites.iloc[ind.reshape(1, -1)[0], :].port_id.values.astype('int'),
                            df['id'].values))
    # define the sql statement
    sql_insert = f"INSERT INTO {target_table} (nearest_site_dist_km, nearest_site_id, id) " \
                 "VALUES(%s, %s, %s);"

    # write to db
    loc_conn = gsta.connect_psycopg2(db_config.colone_cargo_params, print_verbose=False)
    c = loc_conn.cursor()
    c.executemany(sql_insert, (data.tolist()))
    loc_conn.commit()
    c.close()
    loc_conn.close()
    print(f'UID {uid[0]} complete in:', datetime.datetime.now() - iteration_start)



#%% Create "nearest_site" table in the database.
conn = gsta.connect_psycopg2(db_config.colone_cargo_params)
c = conn.cursor()
c.execute(f"""DROP TABLE IF EXISTS {target_table}""")
conn.commit()
c.execute(f"""CREATE TABLE IF NOT EXISTS {target_table}
(   id int,
    nearest_site_id int ,
    nearest_site_dist_km float
);""")
conn.commit()
c.close()
conn.close()

#%% get uid lists
conn = gsta.connect_psycopg2(db_config.colone_cargo_params, print_verbose=False)
c = conn.cursor()
c.execute(f"""SELECT DISTINCT(uid) FROM {source_table};""")
uid_list = c.fetchall()
c.close()
conn.close()
#%%
# establish the connection

first_tick = datetime.datetime.now()
print('Starting Processing at: ', first_tick.time())

# execute the function with pooled workers
if __name__ == '__main__':
    with Pool(workers) as p:
        p.map(calc_nn, uid_list)

last_tock = datetime.datetime.now()
lapse = last_tock - first_tick
print('Processing Done.  Total time elapsed: ', lapse)
conn.close()

#%% build index and add foreign keys
print('Building index...')
conn = gsta.connect_psycopg2(db_config.colone_cargo_params, print_verbose=False)
c = conn.cursor()
c.execute(f"""CREATE INDEX if not exists {target_table}_idx 
            on {target_table} (id);""")
conn.commit()
print('Index built.')
print('Adding foreign keys...')
c.execute(f"""ALTER TABLE {target_table} ADD CONSTRAINT id_to_id FOREIGN KEY (id) REFERENCES ais_cargo.public.{source_table} (id)""")
conn.commit()
c.execute(f"""ALTER TABLE {target_table} ADD CONSTRAINT {target_table}_id_to_site_id FOREIGN KEY ({target_table}_id) REFERENCES ais_cargo.public.sites (site_id)""")
conn.commit()
conn.close()
print('Foreign keys built.')
