# -*- coding: utf8 -*-
import os
import json
import re
import codecs
import urllib
from datetime import date, datetime
from HTMLParser import HTMLParser
from shutil import copyfile

## TODO: avoid doing this!
import sys
reload(sys)
sys.setdefaultencoding('utf8')

from bs4 import BeautifulSoup, Tag
import phpserialize
import pymysql.cursors
import simplejson as json

from config import config
from db import DBConn
from db.query import get_shorten_urls
from db.query import get_wp_terms
from db.query import get_wp_categories
from db.query import get_wp_tags
from db.query import get_wp_users
from db.query import get_wp_posts_count
from db.query import get_wp_posts
from db.query import get_all_wp_posts
from db.query import get_wp_metadata_by_post_id
from db.query import get_all_s3_images_url
from db.query import get_thumb_image_by_post
from db.query import get_sponsors
from db.query import get_features
import helpers
from tools import Debug


orig_prettify = BeautifulSoup.prettify
r = re.compile(r'^(\s*)', re.MULTILINE)
def prettify(self, encoding=None, formatter="minimal", indent_width=4):
    return r.sub(r'\1' * indent_width, orig_prettify(self, encoding, formatter))
BeautifulSoup.prettify = prettify


if __name__ == '__main__':
    ## init logger
    d = Debug(level=4, color=True)

    db_conn = None
    try:
        d.info('connect to database ...')
        db_conn = DBConn(config['dev']['db'])
        d.info('[OK]\n')
    except Exception as e:
        d.error(e)
        exit()

    cursor = db_conn.get_cursor()

    ## init directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.abspath(os.path.join(current_dir, os.pardir, 'output'))
    output_dirs = ['wp_users', 'wp_posts', 'categories', 'tags', 's3_images']
    helpers.create_dirs(output_dir, output_dirs)

    ## get shorten url mappings
    shorten_url_dict = get_shorten_urls(cursor)
    shorten_url_keys = shorten_url_dict.keys()

    shorten_url_id = 1
    for k in shorten_url_dict:
        shorten_url_dict[k]['id'] = shorten_url_id
        shorten_url_id += 1

        shorten_url_dict[k]['link'] = shorten_url_dict[k]['link'].replace('https://prd.localhost//', '/')
        shorten_url_dict[k]['link'] = shorten_url_dict[k]['link'].replace('https://prd.localhost/', '/')

    output_filepath = output_dir + '/link_short_code.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(shorten_url_dict, default=helpers.json_serial, indent=4, encoding='utf-8'))


    ## load wp_terms
    wp_term_dict = get_wp_terms(cursor)


    ## DUMP features
    features = get_features(cursor)
    for s in features:
        if s['term_id'] == 633:
            s['slug'] = 'stock-test'

    # add alias categories to series ( https://prd.localhost/wp-admin/post.php?post=127521&action=edit )
    features += [
        {
            "term_group": 1,
            "term_id": 1001,
            "name": "Some Title Here",
            "slug": "feature-test",
        },
    ]

    output_filepath = output_dir + '/features.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(features, default=helpers.json_serial, indent=4, encoding='utf-8'))


    ## DUMP sponsors
    s = get_sponsors(cursor)
    sponsors = []
    for i in s:
        p = phpserialize.loads(i['meta_value'].encode('utf-8'))
        if p['name'] != "" and p['image'] != "" and p['link'] != "":
            sponsors.append({
                'term_id': i['term_id'],
                'name': p['name'],
                'image': p['image'],
                'link': p['link'],
            })
    output_filepath = output_dir + '/sponsors.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(sponsors, default=helpers.json_serial, indent=4, encoding='utf-8').decode('unicode-escape').encode('utf8'))


    ## START dump categories
    d.info('dump categories ...')
    cat_dict, cat_results = get_wp_categories(cursor, wp_term_dict)
    h = HTMLParser()
    for i in cat_results:
        i['name'] = h.unescape(i['name'])

    output_filepath = output_dir + '/categories/categories.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(cat_results, default=helpers.json_serial, indent=4, encoding='utf-8'))

    d.info('[OK] => {}\n'.format(output_filepath))
    ## END of dump categories


    ## START dump tags
    d.info('dump tags ...')
    post_tag_dict, post_tag_results = get_wp_tags(cursor, wp_term_dict)
    output_filepath = output_dir + '/tags/tags.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(post_tag_results, default=helpers.json_serial, indent=4, encoding='utf-8').decode('unicode-escape').encode('utf8'))

    d.info('[OK] => {}\n'.format(output_filepath))
    ## END of dump tags


    ## dump wp_users
    d.info('dump users ...')
    wp_user_dict, wp_user_lists = get_wp_users(cursor)
    wp_user_lists = helpers.wp_users_replacement(wp_user_lists)
    output_filepath = output_dir + '/wp_users/wp_users.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(wp_user_lists, default=helpers.json_serial, indent=4, encoding='utf-8'))

    d.info('[OK] => {}\n'.format(output_filepath))
    ## END of wp_users

    ## TEST
    #ps = get_all_wp_posts(cursor)
    #n = []
    #d = {}
    #tt = 0
    #for p in ps:
    #    pb = BeautifulSoup(p['post_content'], 'lxml')
    #    c = 0
    #    r = []
    #    for i in pb():
    #        if isinstance(i, Tag):
    #            if i.name == 'table':
    #                c += 1
    #                d[p['ID']] = ''

    #    if c > 0:
    #        tt += 1
    #        n.append({'_id': p['ID'], 'count': c})

    #class SetEncoder(json.JSONEncoder):
    #    def default(self, obj):
    #       if isinstance(obj, set):
    #          return list(obj)
    #       return json.JSONEncoder.default(self, obj)

    #with codecs.open('s.log', 'w+', 'utf8') as f:
    #    f.write(json.dumps({'total': tt, 'd': sorted(d)}, indent=2, cls=SetEncoder))
    #exit()

    ## dump articles
    d.info('dump articles ...')
    posts_count = get_wp_posts_count(cursor)
    d.info('total count: {}'.format(posts_count))
    per = 1000
    page = 0

    wp_links = {}
    wp_link_counter = 101

    imported_idd ={}
    with open(current_dir + '/../deps/imported_ids.json') as f:
        _d = json.load(f)
        for x in _d['array_agg']:
            imported_idd[x] = 1

    all_image_urls = {}
    for i in xrange(posts_count / per + 1):
        #if i > 0:
        #    break

        wp_posts = get_wp_posts(cursor, per=per, page=(i+1))
        wp_post_lists = helpers.wp_posts_replacement(cursor, wp_posts, shorten_url_dict, shorten_url_keys, cat_dict, post_tag_dict, imported_idd)
        output_filepath = output_dir + '/wp_posts/wp_posts_{}.json'.format(i)

        for k, wp_post in enumerate(wp_post_lists):
            if 'wplink' in wp_post:
                if wp_post['wplink'][0] not in wp_links:
                    wp_links[wp_post['wplink'][0]] = {
                        'id': wp_link_counter,
                        'data': wp_post['wplink'][1],
                    }
                    wp_link_counter += 1

                wp_post_lists[k]['wplink_id'] = wp_links[wp_post['wplink'][0]]['id']

            res = get_thumb_image_by_post(cursor, wp_post['id'])
            thumb_url = "" if res is None else res['guid']
            wp_post['thumb_url'] = thumb_url

            for image_url in wp_post['image_urls']:
                if image_url.find('https://prd.localhost/wp-content/uploads/') != -1:
                    all_image_urls[image_url] = 1

        with codecs.open(output_filepath, 'w+', 'utf-8') as f:
            f.write(json.dumps(wp_post_lists, default=helpers.json_serial, indent=4))

        d.info('[OK] => {}\n'.format(output_filepath))

        # pick up needed images
        #for wp_post in wp_post_lists:
        #    for image_url in wp_post['image_urls']:
        #        matches = re.findall(r'^https://prd.localhost/wp-content/uploads/(.*)$', image_url)

        #        for i in matches:
        #            if not os.path.exists(output_dir + '/wp-content-dl/uploads/' + i):
        #                urllib.urlretrieve(image_url, output_dir + '/wp-content-dl/uploads/' + i)

        #            dst_fn = output_dir + '/wp-content-real/' + i
        #            if not os.path.exists(dst_fn):
        #                copyfile(output_dir + '/wp-content-dl/uploads/' + i, dst_fn)

    output_filepath = output_dir + '/wp_posts/wp_links.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(wp_links, default=helpers.json_serial, indent=4))

    output_filepath = output_dir + '/all_image_urls.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(all_image_urls, default=helpers.json_serial, indent=4))

    ## dump s3_images links
    """
    d.info('dump s3 image links ...')
    s3_image_links = get_all_s3_images_url(cursor)
    d.info('total count: {}'.format(len(s3_image_links)))

    s3_image_results = {}
    for s3_image_link in s3_image_links:
        cdn_wp_online_links = phpserialize.loads(s3_image_link['meta_value'])['cdn-wp-online']
        post_id = s3_image_link['post_id']

        s3_image_results[post_id] = cdn_wp_online_links

    output_filepath = output_dir + '/s3_images/s3_images.json'
    with codecs.open(output_filepath, 'w+', 'utf-8') as f:
        f.write(json.dumps(s3_image_results, default=helpers.json_serial, indent=4))

    d.info('[OK] => {}\n'.format(output_filepath))
    """

    db_conn.close()
