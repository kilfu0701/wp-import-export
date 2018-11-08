# -*- coding: utf8 -*-
import os
import re
import json
import argparse
import urllib
from HTMLParser import HTMLParser
import codecs
import locale
import sys
import shutil

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup
import Levenshtein
from PIL import Image

from tools import Debug
import helpers
from config import config
from decorators import extend_bs4_prettify

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

# override BeautifulSoup.prettify
orig_prettify = BeautifulSoup.prettify
r = re.compile(r'^(\s*)', re.MULTILINE)
def prettify(self, encoding=None, formatter="minimal", indent_width=4):
    return r.sub(r'\1' * indent_width, orig_prettify(self, encoding, formatter))
BeautifulSoup.prettify = prettify


class WPImporter:
    def __init__(self, *args, **kwargs):
        self.start_idx = kwargs['start_idx'] if 'start_idx' in kwargs else 0
        self.end_idx = kwargs['end_idx'] if 'end_idx' in kwargs else 0
        self.env = kwargs['env'] if 'env' in kwargs else 'dev'
        self.conf = config[self.env]
        self.d = Debug(level=4, color=True)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_dir = os.path.abspath(os.path.join(self.current_dir, os.pardir))
        self.admin_url = self.conf['url']['admin']
        self._default_image_id = 2

    def get_csrf_token_from_page(self, url):
        r = self.s.get(url, verify=False)
        soup = BeautifulSoup(r.text, "lxml")
        return soup.find('input', {'name': '_csrf'}).get('value')

    def login(self):
        self.s = requests.Session()
        #r = self.s.get('{}/auth/login'.format(self.admin_url), verify=False)
        #csrf_token = r.cookies['_csrf']
        csrf_token = self.get_csrf_token_from_page('{}/auth/login'.format(self.admin_url))
        p = {
            'email': self.conf['account']['email'],
            'password': self.conf['account']['password'],
            '_csrf': csrf_token
        }
        self.s.post('{}/auth/login'.format(self.admin_url), data=p)

    def import_categories(self):
        with open(self.project_dir + '/output/categories/categories.json', 'r') as f:
            ## import categories
            self.d.info('start importing categories ...')
            csrf_token = self.get_csrf_token_from_page('{}/categories/new'.format(self.admin_url))
            categories = json.load(f)
            categories_count = len(categories)
            counter = 1
            cur_id = 0
            while len(categories) > 0:
                category = categories.pop(0)

                if category['id'] > cur_id:
                    cur_id = category['id']

                if category['parent'] > cur_id:
                    categories.append(category)
                    continue

                category['import_id'] = category['id']
                del category['id']

                category['parent_id'] = category['parent']
                del category['parent']

                category['_csrf'] = csrf_token
                z = self.s.post('{}/api/v1/categories/new'.format(self.admin_url), json=category, headers=self._create_headers(csrf_token))
                result = json.loads(z.text)
                progress_info = '({}/{})'.format(counter, categories_count)
                if 'errors' in result['payload']:
                    for k in result['payload']['errors']:
                        self.d.error('ERROR', progress_info, 'cat_id={}'.format(category['import_id']), k, result['payload']['errors'][k])
                else:
                    self.d.log('Done.', progress_info, result['payload']['message'])

                counter += 1

    def import_tags(self):
        with open(self.project_dir + '/output/tags/tags.json', 'r') as f:
            ## import tags
            csrf_token = self.get_csrf_token_from_page('{}/tags/new'.format(self.admin_url))
            tags = json.load(f)
            for tag in tags:
                tag['import_id'] = tag['id']
                del tag['id']
                tag['_csrf'] = csrf_token
                z = s.post('{}/api/v1/tags/new'.format(self.admin_url), json=tag, headers=self._create_headers(csrf_token))
                result = json.loads(z.text)
                if 'errors' in result['payload']:
                    for k in result['payload']['errors']:
                        self.d.error('ERROR', progress_info, 'tag_id={}'.format(category['import_id']), k, result['payload']['errors'][k])
                else:
                    self.d.log('Done.', result['payload']['message'])


    def import_operators(self):
        with open(self.project_dir + '/output/wp_users/wp_users.json', 'r') as f:
            ## import operators
            self.d.info('start importing operators ...')
            csrf_token = self.get_csrf_token_from_page('{}/operators/new'.format(self.admin_url))
            operators = json.load(f)
            operators_count = len(operators)
            counter = 1
            for operator in operators:
                operator['import_id'] = operator['id']
                del operator['id']

                operator['_csrf'] = csrf_token
                z = self.s.post('{}/api/v1/operators/new'.format(self.admin_url), json=operator, headers=self._create_headers(csrf_token))
                result = json.loads(z.text)
                progress_info = '({}/{})'.format(counter, operators_count)
                if 'errors' in result['payload']:
                    for k in result['payload']['errors']:
                        self.d.error('ERROR', progress_info, 'operator_id={}'.format(operator['import_id']), k, result['payload']['errors'][k])
                else:
                    self.d.log('Done.', progress_info, result['payload']['message'])

                counter += 1

    def import_articles_with_images(self):
        self.import_articles(with_image=True)

    def update_article_image(self):
        """
            COPY (SELECT ROW_TO_JSON(t) FROM (SELECT articles.id, image_files.filename FROM articles
                join images on images.id = articles.image_id join image_files on images.id = image_files.image_id) t) TO '/tmp/article_image_relations.json';
            mv /tmp/article_image_relations.json /var/lib/postgresql/data/
            mv $DOCKER_ALIAS/data/article_image_relations.json ~/wordpress-split-data/deps/
        """
        contents = []
        self.air = {}
        with open(self.project_dir + '/deps/article_image_relations.json', 'r') as f:
            contents = f.readlines()

        for line in contents:
            j = json.loads(line.strip())
            self.air[j['id']] = j

        self.import_articles(with_image=True, update_only=True, save_to_local=True)

    def import_articles(self, with_image=False, update_only=False, save_to_local=False):
        h = HTMLParser()

        self.uii = {}
        with open(self.project_dir + '/deps/upload_images_id.json.c') as f:
            self.uii = json.load(f)

        features_alias = {}
        with open(self.project_dir + '/output/features.json', 'r') as f:
            series = json.load(f)
            categories = []
            with open(self.project_dir + '/output/categories/categories.json', 'r') as f:
                categories = json.load(f)

            for s in series:
                if s['term_group'] == 1:
                    for category in categories:
                        if category['slug'] == s['slug']:
                            features_alias[category['id']] = s
                            break

        for idx in xrange(self.start_idx, self.end_idx + 1):
            input_file = self.project_dir + '/output/wp_posts/wp_posts_{}.json'.format(idx)
            with open(input_file, 'r') as f:
                ## import articles
                self.d.info('start importing articles ...')
                self.d.info('read file ... {}'.format(input_file))
                csrf_token = self.get_csrf_token_from_page('{}/articles/new'.format(self.admin_url))
                articles = json.load(f)
                articles_count = len(articles)
                counter = 1
                operator_ids = self._get_operators_ids()
                for article in articles:
                    # replace cdn url into /media/image/:id
                    xds = re.findall('(https://stg.localhost/640/480/uploads/(.*))"', article['html_content'])
                    article['html_content'] = self._replace_image_url_to_media(xds, article['html_content'])

                    # replace s3 url into /media/image/:id
                    xds = re.findall('(https://cdn-prd.s3-ap-northeast-1.amazonaws.com/wp-content/uploads/(.*))"', article['html_content'])
                    article['html_content'] = self._replace_image_url_to_media(xds, article['html_content'])

                    if article['author_id'] not in operator_ids:
                        self.d.debug('operator id not exists. Set to author_id = 1.')
                        article['author_id'] = 1

                    article['import_id'] = article['id']

                    # set one space if subtitle is empty
                    if article[u'sub_title'] == '':
                        article[u'sub_title'] = ' '
                    else:
                        article[u'sub_title'] = article[u'sub_title'][:60]

                    if u'published_at' in article:
                        article['status'] = 2

                    if article['series_id'] != 0:
                        article['feature_ids'] = [article['series_id']]
                    else:
                        article['feature_ids'] = []

                    # limit title to 60 words
                    article[u'title'] = h.unescape(article[u'title'][:60])

                    # limit meta_description to 120 words
                    article[u'meta_description'] = article[u'meta_description'][:100]

                    if article[u'meta_description'] == '':
                        article[u'meta_description'] = article[u'title']

                    # make content & html_content the same.
                    article[u'content'] = article['html_content']

                    # do not import tag_ids
                    article[u'tag_ids'] = []

                    article['_csrf'] = csrf_token

                    article['html_content'] = h.unescape(article['html_content'])

                    # make category <-> features alias
                    if article['category_id'] != 0 and article['category_id'] in features_alias:
                        article['feature_ids'].append(features_alias[article['category_id']]['term_id'])

                    article['image_id'] = self._default_image_id
                    if save_to_local:
                        if article['id'] in self.air:
                            article['image_id'] = self.air[article['id']]['image_id']
                        else:
                            article['image_id'] = self._default_image_id

                    z = None
                    if update_only:
                        article = self._upload_media_image(article, upload_flag=False)
                        #del article['image_id']
                        z = self.s.put('{}/api/v1/articles/{}'.format(self.admin_url, article['import_id']), json=article, headers=self._create_headers(csrf_token))
                    else:
                        z = self.s.post('{}/api/v1/articles/new'.format(self.admin_url), json=article, headers=self._create_headers(csrf_token))

                    result = json.loads(z.text)
                    progress_info = '({}/{})'.format(counter, articles_count)
                    if 'errors' in result['payload']:
                        for k in result['payload']['errors']:
                            self.d.error('ERROR', progress_info, 'id={}'.format(article['import_id']), k, result['payload']['errors'][k], article['category_id'])
                    else:
                        if result['status'] == 'Not Found':
                            self.d.error('Not Found.', progress_info, 'id={}'.format(article['import_id']))
                        else:
                            self.d.log('Done.', progress_info, 'id={}'.format(article['import_id']), result['payload']['message'])

                            if with_image:
                                if save_to_local:
                                    article = self._upload_media_image(article, upload_flag=False, save_to_local=True)
                                else:
                                    article = self._upload_media_image(article)

                                    # update image_id
                                    self._update_article_image_id(article)

                    counter += 1

    def import_widgets(self):
        link_short_code_dict = {}
        with open(self.project_dir + '/output/link_short_code.json', 'r') as f:
            link_short_code_dict = json.load(f)

        with open(self.project_dir + '/output/wp_posts/wp_links.json', 'r') as f:
            ## import wplink as widgets
            csrf_token = self.get_csrf_token_from_page('{}/widgets/new'.format(self.admin_url))
            wplinks = json.load(f)
            for key in wplinks:
                # insert widget
                wplink = wplinks[key]
                content = u'<div class="recommend-links"><h2 class="title">【編集部のオススメ記事】</h2><ul class="links">{}</ul></div>'.format(
                    ''.join([u'<li><a href="{}"><i class="icons-right _color-darkgray"></i>{}</a></li>'.format(wplink['data'][k][0], wplink['data'][k][1]) for k in wplink['data']])
                )

                widget_title = ",".join([k for k in wplink['data']])[:60]
                content = content.replace(u'https://prd.localhost/archives', u'/archives')
                content_soup = BeautifulSoup(content, "lxml")

                if content_soup.html is not None:
                    content_soup.html.unwrap()

                if content_soup.body is not None:
                    content_soup.body.unwrap()

                if wplink['id'] == 124:
                    widget_title += ' '

                widget_data = {
                    'import_id': wplink['id'],
                    'name': widget_title,
                    'content': ' ', #content_soup.prettify(),
                    'type_id': 10, # おすすめ記事リンク
                    'link_ids': [link_short_code_dict[k]['id'] for k in wplink['data']]
                }
                widget_data['_csrf'] = csrf_token
                z = self.s.post('{}/api/v1/widgets/new'.format(self.admin_url), json=widget_data, headers=self._create_headers(csrf_token))
                result = json.loads(z.text)
                if 'errors' in result['payload']:
                    for k in result['payload']['errors']:
                        self.d.error('ERROR', k, result['payload']['errors'][k])
                else:
                    self.d.log('Done.', result['payload']['message'])

                # insert panel
                panel_data = {
                    'import_id': wplink['id'],
                    'name': widget_title,
                    'type_id': 7,
                    'widget_ids': [wplink['id']],
                }
                z = self.s.post('{}/api/v1/panels/new'.format(self.admin_url), json=panel_data, headers=self._create_headers(csrf_token))
                result = json.loads(z.text)
                if 'errors' in result['payload']:
                    for k in result['payload']['errors']:
                        self.d.error('ERROR', k, result['payload']['errors'][k])
                else:
                    self.d.log('Done.', wplink['id'], result['payload']['message'])


    def import_feature(self):
        with open(self.project_dir + '/output/features.json', 'r') as f:
            csrf_token = self.get_csrf_token_from_page('{}/features/new'.format(self.admin_url))
            series = json.load(f)
            for s in series:
                # insert widget
                feature_data = {
                    'import_id': s['term_id'],
                    'author_id': 1001,
                    'title': s['name'],
                    'slug': s['slug'],
                    'image_id': 50002, # self._default_image_id,
                    'description': ' ',
                    '_csrf': csrf_token,
                }
                z = self.s.post('{}/api/v1/features/new'.format(self.admin_url), json=feature_data, headers=self._create_headers(csrf_token))
                result = json.loads(z.text)
                if 'errors' in result['payload']:
                    for k in result['payload']['errors']:
                        self.d.error('ERROR', k, result['payload']['errors'][k], s['term_id'], s['name'])
                else:
                    self.d.log('Done.', result['payload']['message'])

    def import_link_short_code(self):
        with open(self.project_dir + '/output/link_short_code.json', 'r') as f:
            # TODO: change to correct url
            csrf_token = self.get_csrf_token_from_page('{}/features/new'.format(self.admin_url))
            link_short_codes = json.load(f)
            for key in link_short_codes:
                lsc_data = {
                    'import_id': link_short_codes[key]['id'],
                    'name': key,
                    'display_name': link_short_codes[key]['title'],
                    'href': link_short_codes[key]['link'],
                    '_csrf': csrf_token,
                }
                z = self.s.post('{}/api/v1/link_short_codes/new'.format(self.admin_url), json=lsc_data, headers=self._create_headers(csrf_token))
                result = json.loads(z.text)
                if 'errors' in result['payload']:
                    for k in result['payload']['errors']:
                        self.d.error('ERROR', k, result['payload']['errors'][k])
                else:
                    self.d.log('Done.', result['payload']['message'])

    def download_images(self):
        input_file = self.project_dir + '/output/s3_images/s3_images.json'
        with open(input_file, 'r') as f:
            ## import articles
            self.d.info('read file ... {}'.format(input_file))
            s3_images = json.load(f)
            print len(s3_images.keys())

            for d in s3_images:
                for origin_url in s3_images[d]:
                    # create dirs
                    image_path = origin_url.split('https://prd.localhost/')[1]
                    image_dir = '/'.join(image_path.split('/')[:-1])
                    helpers.create_dirs(self.project_dir + '/output', [image_dir])

                    s3_url = s3_images[d][origin_url]
                    urllib.urlretrieve(origin_url, 'output/' + image_dir + '/' + origin_url.split('/')[-1])


    def _get_operators_ids(self):
        with open(self.project_dir + '/output/wp_users/wp_users.json', 'r') as f:
            operators = json.load(f)
            return [operator['id'] for operator in operators]


    def _upload_media_image(self, article, upload_flag=True, save_to_local=False):
        thumb_url = article['thumb_url']

        if thumb_url == "":
            if len(article['image_urls']) > 0:
                thumb_url = article['image_urls'][0]
            else:
                article['image_id'] = self._default_image_id
                return article

        fn = thumb_url.split('/')[-1]

        open_fn = fn
        file_exist_flag = os.path.isfile(self.project_dir + '/output/wp-content-dl/uploads/' + fn)
        if not file_exist_flag:
            for ch in '12345':
                tmp = os.path.splitext(fn)
                open_fn = '{}{}{}'.format(tmp[0], ch, tmp[1])

                if os.path.isfile(self.project_dir + '/output/wp-content-dl/uploads/' + open_fn):
                    file_exist_flag = True
                    break

        if not file_exist_flag:
            # fetch image
            image_url = 'https://prd.localhost/wp-content/uploads/{}'.format(fn)
            self.d.log('no image file found. start fetch files ...', image_url)
            image_dir = 'wp-content-dl'
            helpers.create_dirs(self.project_dir + '/output', [image_dir])
            urllib.urlretrieve(image_url, 'output/' + image_dir + '/uploads/' + image_url.split('/')[-1])
            open_fn = fn
            file_exist_flag = True

        image_path = self._get_image_full_path(open_fn)
        is_image = False
        try:
            with Image.open(image_path) as f:
                is_image = True
        except:
            pass

        if file_exist_flag and is_image:
            ## use default image
            if fn == 'logo_thumbnail1.jpg':
                article['image_id'] = self._default_image_id
                return article

            ## resize image before upload
            self._resize_eyecatch_image(image_path, fn)

            if upload_flag:
                self.d.debug('start upload image... {}'.format(fn))
                result = self._create_image_info()
                image_file_id, image_id, upload_url, content_type = self._generate_image_file_id(fn, result['payload']['Id'])
                #self.d.debug('upload url = {}'.format(upload_url))

                with open('/tmp/{}'.format(fn), 'r') as f:
                    if upload_flag:
                        image_data = f.read()
                        headers = {
                            'content-type': content_type,
                            'content-length': str(len(image_data)),
                        }
                        r = self.s.put(upload_url, data=image_data, headers=headers)

                    if (upload_flag and r.status_code == 200) or not upload_flag:
                        if upload_flag:
                            # doing image validation. ( /api/batch/media/image/validate/:id )
                            self.s.get('{}/api/batch/media/image/validate/{}'.format(self.admin_url, image_file_id))
                            article['image_id'] = image_id
                            self.d.debug('image uploaded. post_id={}, image_id={}'.format(article['id'], image_file_id))

                        # remove img tag in html_content
                        #article = self._remove_eyecatch_image_in_content(article)
                    else:
                        article['image_id'] = self._default_image_id
                        self.d.error('error uploading image. ID={}'.format(article['id']))

                # remove tmp image after upload finished
                os.remove(self.conf['path']['tmp_image'] + '/' + fn)

            if save_to_local:
                dst_dir = '/tmp/u/' + self.air[article['id']]['filename'].split('/')[0]
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)

                dst_file = '/tmp/u/' + self.air[article['id']]['filename']
                src_file = self.conf['path']['tmp_image'] + '/' + fn
                if os.path.exists(dst_file):
                    os.remove(dst_file)

                try:
                    shutil.move(src_file, dst_file)
                except:
                    pass

        else:
            article['image_id'] = self._default_image_id
            self.d.error('thumb image not found. [post_id = {}][{}]'.format(article['id'], fn))

        return article

    def _remove_eyecatch_image_in_content(self, article):
        content_soup = BeautifulSoup(article['html_content'], 'lxml')
        for img_tag in content_soup.findAll('img'):
            # remove "?asd=1" parameter
            img_tag['src'] = img_tag['src'].split('?')[0]

            # remove "(1)" something like medium_210421689(1).jpg
            img_tag['src'] = re.sub(r'\(\d\)', '', img_tag['src'])

            img_fn = img_tag['src'].split('/')[-1]
            split_by_dot = img_fn.split('.')
            split_by_hypen = split_by_dot[0].split('-')

            # handle some rare case which the url doesn't have file ext
            if len(split_by_dot) == 1:
                split_by_dot.append('')

            img_fn2 = '-'.join(split_by_hypen[0:len(split_by_hypen) - 1]) + '.' + split_by_dot[1]
            match_rate = 0.95
            o = os.path.splitext(img_fn)
            m = re.match(r'{}\d?\.{}'.format(o[0], o[1][1:]), img_fn)
            if Levenshtein.ratio(unicode(img_fn), unicode(fn)) > match_rate or Levenshtein.ratio(unicode(img_fn2), unicode(fn)) > match_rate or m is not None:
                img_tag.extract()
                content_soup.html.unwrap()
                content_soup.body.unwrap()

                article['html_content'] = content_soup.prettify(indent_width=2)
                # only for first one
                break
            else:
                self.d.error("img_tag's not matched. {} / {}".format(img_fn, fn))

    def _create_image_info(self):
        # https://admin.localhost/api/v1/media/image/new
        # alt= , caption= , use_type=4
        csrf_token = self.get_csrf_token_from_page('{}/media'.format(self.admin_url))
        create_image_params = {
            'alt': '',
            'caption': '',
            'use_type': 4,
        }
        result = self.s.post('{}/api/v1/media/image/new'.format(self.admin_url), json=create_image_params, headers=self._create_headers(csrf_token))
        return json.loads(result.text)

    def _generate_image_file_id(self, fn, fid):
        # /api/v1/media/image/3/upload/new
        # POST
        # request_filename: "randString.png"
        csrf_token = self.get_csrf_token_from_page('{}/media'.format(self.admin_url))
        create_upload_url_params = {
            'request_filename': fn,
        }
        r = self.s.post('{}/api/v1/media/image/{}/upload/new'.format(self.admin_url, fid), json=create_upload_url_params, headers=self._create_headers(csrf_token))
        result = json.loads(r.text)
        return (result['payload']['ImageFileId'], result['payload']['ImageFileId2'], result['payload']['UploadURL'], result['payload']['ContentType'])

    def _get_image_full_path(self, fn):
        return self.project_dir + '/output/wp-content-dl/uploads/' + fn

    def _get_admin_url(self):
        return self.conf['url']['admin']

    def _create_headers(self, csrf_token):
        return {
            'x-csrf-token': csrf_token,
            'content-type': 'application/json;charset=UTF-8',
        }

    def _resize_eyecatch_image(self, image_path, fn):
        basewidth = 600
        baseheight = 400
        img = Image.open(image_path)
        if img.size[0] < basewidth:
            wpercent = (basewidth/float(img.size[0]))
            hsize = int((float(img.size[1]) * float(wpercent)))
            img = img.resize((basewidth, hsize), Image.ANTIALIAS)

        if img.size[1] < baseheight:
            wpercent = (baseheight/float(img.size[1]))
            wsize = int((float(img.size[0]) * float(wpercent)))
            img = img.resize((wsize, baseheight), Image.ANTIALIAS)

        ratio = float(img.size[0]) / float(img.size[1])

        y1 = (img.size[1] - baseheight) / 2
        y2 = y1 + baseheight
        x1 = (img.size[0] - basewidth) / 2
        x2 = x1 + basewidth

        if ratio > 1.5:
            w = int(float(img.size[1]) * 1.5)
            x1 = (img.size[0] - w) / 2
            x2 = x1 + w
            img = img.crop((x1, 0, x2, img.size[1]))
        else:
            h = int(float(img.size[0]) / 1.5)
            y1 = (img.size[1] - h) / 2
            y2 = y1 + h
            img = img.crop((0, y1, img.size[0], y2))

        if fn.find('.') == -1:
            fn = 'rand.' + fn

        img.save(self.conf['path']['tmp_image'] + '/' + fn)

    def _update_article_image_id(self, article):
        csrf_token = self.get_csrf_token_from_page('{}/articles/edit/{}'.format(self.admin_url, article['id']))
        update_params = article
        r = self.s.put('{}/api/v1/articles/{}'.format(self.admin_url, article['id']), json=update_params, headers=self._create_headers(csrf_token))
        result = json.loads(r.text)
        if r.status_code == 200:
            self.d.log('image_id update Done.', article['id'], result['payload']['message'])
        else:
            if 'errors' in result['payload']:
                for k in result['payload']['errors']:
                    self.d.error('ERROR', k, result['payload']['errors'][k])

    def _replace_image_url_to_media(self, xds, article_html_content):
        for xd in xds:
            xt = xd[0].split(u'"')[0]
            xr = xd[1].split(u'"')[0]
            try:
                article_html_content = article_html_content.replace(xt, 'https://admin.localhost/media/image/{}'.format(self.uii[xr]))
            except:
                self.d.error('failed replace image url to media ... key =', xr)

        return article_html_content


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Import prd.localhost wordpress data.')
    parser.add_argument('--type', help='import types. [all | category | operator | image]', default='all')
    parser.add_argument('--start', help='number of json file.', type=int, default=0)
    parser.add_argument('--end', help='number of json file.', type=int, default=0)
    parser.add_argument('--env', help='env. [dev | stage | prod]', default='dev')
    args = parser.parse_args()

    start_idx = args.start
    end_idx = args.end

    importer = WPImporter(**{'start_idx': start_idx, 'end_idx': end_idx, 'env': args.env})
    importer.login()
    if args.type == 'all':
        importer.import_categories()
        importer.import_operators()
        importer.import_link_short_code()
        #importer.import_widgets()
        importer.import_feature()
        importer.import_articles()

    elif args.type == 'category':
        importer.import_categories()

    elif args.type == 'operator':
        importer.import_operators()

    #elif args.type == 'article':
    #    importer.import_articles()

    #elif args.type == 'widget':
    #    importer.import_widgets()

    #elif args.type == 'image':
    #    importer.download_images()

    elif args.type == 'feature':
        importer.import_feature()

    elif args.type == 'link_short_code':
        importer.import_link_short_code()

    elif args.type == 'article_with_image':
        importer.import_articles_with_images()

    elif args.type == 'update_article_image':
        importer.update_article_image()

    #elif args.type == 'update_article':
    #    importer.import_articles(False, True)
