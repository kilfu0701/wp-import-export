# -*- coding: utf-8 -*-
##
## python src/gen_images_sql.py > output/insert_upload_images.sql
##
import os
import codecs
from os import listdir
from os.path import isfile, join

import simplejson as json

current_dir = os.path.dirname(os.path.abspath(__file__))
upload_real_dir = current_dir + '/../output/wp-content-real'
output_dir = os.path.abspath(os.path.join(current_dir, os.pardir, 'output'))

start_count = 107040

onlyfiles = [f for f in listdir(upload_real_dir) if isfile(join(upload_real_dir, f))]

r = {}
with open(current_dir + '/../deps/upload_images_id.json.c', 'r') as f:
    d = json.load(f)

for f in onlyfiles:
    if f in d:
        continue

    print "INSERT INTO images (id, operator_id, use_type, alt, caption, deleted_flg, created_at, updated_at) VALUES ({}, 1001, 1, ' ', ' ', false, '2017-10-14 16:32:54.603798+09', '2017-10-14 16:32:54.603798+09');".format(start_count)
    print "INSERT INTO image_files (id, image_id, operator_id, filename, width, height, filesize, digest, status, deleted_flg, created_at, updated_at) VALUES ({}, {}, 1001, 'uploads/{}', NULL, NULL, NULL, NULL, 1, false, '2017-10-25 16:31:10.300336+09', '2017-10-25 16:31:10.300336+09');".format(start_count, start_count, f)
    r[f] = start_count

    start_count += 1

output_filepath = output_dir + '/upload_images_id.json'
with codecs.open(output_filepath, 'w+', 'utf-8') as f:
    f.write(json.dumps(r, indent=4))
