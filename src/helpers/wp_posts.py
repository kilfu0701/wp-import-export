import re
import hashlib
import phpserialize
from HTMLParser import HTMLParser
import simplejson as json

import helpers
from decorators import extend_bs4_prettify, set_recursion_limit
from bs4 import BeautifulSoup, Comment, Tag, NavigableString

from db.query import get_wp_metadata_by_post_id
from db.query import get_features
from db.query import check_if_fisco
from db.query import xs

fix_nextpage_dicts = {
    117007: [('[nextpage number="" text=""]', '')],
    173175: [('[nextpage number="2"]', '')],
}

#@extend_bs4_prettify
@set_recursion_limit(1500)
def replacement(cursor, wp_posts, shorten_url_dict, shorten_url_keys, cat_dict, post_tag_dict, imported_idd={}):
    features = get_features(cursor)
    feature_ids = [f['term_id'] for f in features]
    wp_post_lists = []
    wp_post_dict = {}
    h = HTMLParser()
    for wp_post in wp_posts:
        # extract wplink and remove all [wplink ...] in content.
        matches = re.findall(r'(\[wplink name="(.*)"\])', wp_post['post_content'])
        short_link_dict = {}
        short_links = []
        for i in matches:
            full, part = i
            if part in shorten_url_keys:
                short_links.append(part)

        if len(short_links) > 0:
            z = hashlib.md5(''.join(sorted(short_links))).hexdigest()
            x = {}
            for short_link in short_links:
                x[short_link] = [shorten_url_dict[short_link]['link'], shorten_url_dict[short_link]['title']]

            wp_post['wplink'] = [z, x]

        # fix newline at <span> & オススメ記事
        wp_post['post_content'] = wp_post['post_content'].replace('\r\n<span', '\r\n\r\n<span')

        # add more 1 newline
        add_newline_lists = ['</h1>', '</h2>', '</h3>', '</h4>', '</h5>', '</table>', '</p>', '</blockquote>', '</ul>', '</ol>']
        for add_newline_list in add_newline_lists:
            wp_post['post_content'] = wp_post['post_content'].replace(add_newline_list, add_newline_list + "\r\n")

        # add <br> if needed
        lists_without_br = ['<table', '<thead', '<tbody', '<td', '<th', '<tr', '</table>', '</thead>', '</tbody>', '</td>', '</th>', '</tr>', '<p>', '</p>', '</li>']
        ts = wp_post['post_content'].split('\r\n\r\n')
        for i, v in enumerate(ts):
            t = ts[i].strip()
            need_replace = True
            for lwb in lists_without_br:
                if t.find(lwb) != -1:
                    need_replace = False
                    break

            if need_replace:
                ts[i] = ts[i].replace('\r\n', '<br>\r\n')

        wp_post['post_content'] = '\r\n\r\n'.join(ts)

        # remove width & height attribute
        wp_post['post_content'] = re.sub(r'(.*) width="\d+"(.*)', r'\1\2', wp_post['post_content'])
        wp_post['post_content'] = re.sub(r'(.*) height="\d+"(.*)', r'\1\2', wp_post['post_content'])

        # replace [caption] to html format
        wp_post['post_content'] = re.sub(r'\[caption(.*)\](.*>)(.*)\[\/caption\]', r'<div class="media">\2<div class="caption">\3</div></div>', wp_post['post_content'])

        # remove [nextpage]
        #wp_post['post_content'] = re.sub(r'\[\/nextpage\]', '', wp_post['post_content'])
        #wp_post['post_content'] = re.sub(r'\[nextpage(.*)\]', '', wp_post['post_content'])

        pid = wp_post['ID']
        wp_post_dict[pid] = wp_post
        wp_post_dict[pid]['meta'] = {}
        wp_post_dict[pid]['related_article_ids'] = []
        wp_post_dict[pid]['related_article_titles'] = []

        wp_postmeta_result = get_wp_metadata_by_post_id(cursor, pid)
        for wp_postmeta in wp_postmeta_result:
            wp_post_dict[wp_postmeta['post_id']]['meta'][wp_postmeta['meta_key']] = wp_postmeta['meta_value']

            if wp_postmeta['meta_key'] == 'simple_related_posts':
                # convert related_articles
                ra_ids = sorted(list(set(map(int, re.findall(r'"(\d+)"', wp_post_dict[wp_postmeta['post_id']]['meta']['simple_related_posts'])))), reverse=True)
                ra_ids = [ra_id for ra_id in ra_ids if not check_if_fisco(cursor, ra_id) and ra_id in imported_idd]
                wp_post_dict[wp_postmeta['post_id']]['related_article_ids'] = ra_ids
                # XXX: set default title
                wp_post_dict[wp_postmeta['post_id']]['related_article_titles'] = ['x' for _ in ra_ids]
                del wp_post_dict[wp_postmeta['post_id']]['meta'][wp_postmeta['meta_key']]

    for k in wp_post_dict:
        _wp_post = wp_post_dict[k]

        # fix html_content. change double newline into <p> tag.
        sps = _wp_post['post_content'].split('\r\n\r\n')
        for idx, val in enumerate(sps):
            if sps[idx][:3] != '<p>':
                sps[idx] = '<p>{}</p>'.format(val)
        _wp_post['post_content'] = '\r\n'.join(sps)

        # insert <br> after some tags.
        _wp_post['post_content'] = re.sub(r'</strong>\r\n', '</strong><br>\r\n', _wp_post['post_content'])
        _wp_post['post_content'] = re.sub(r'</a>\r\n', '</a><br>\r\n', _wp_post['post_content'])
        _wp_post['post_content'] = re.sub(r'<p>【(.*)オススメ(.*)】\r\n', r'<p>【\g<1>オススメ\g<2>】<br>\r\n', _wp_post['post_content'])

        # create soup
        post_content_soup = BeautifulSoup(_wp_post['post_content'], "lxml")
        # remove class,id,name and style in html.
        for tag in post_content_soup():
            if isinstance(tag, Tag):
                for attribute in ["class", "id", "name", "style"]:
                    if tag.name == 'div' and 'class' in tag.attrs and ('media' in tag.attrs['class'] or 'caption' in tag.attrs['class']):
                        continue
                    del tag[attribute]

        # fix html_content. wrap NavigableString into a <p> tag.
        for k, v in enumerate(post_content_soup.body.findAll(recursive=False)):
            if isinstance(v, NavigableString):
                new_p_tag = post_content_soup.new_tag('p')
                if post_content_soup.body.contents[k].strip() == 'nextpage':
                    new_p_tag.append(Comment('nextpage'))
                else:
                    new_p_tag.string = unicode(v)

                post_content_soup.body.contents[k] = new_p_tag

        post_content_soup.html.unwrap()
        post_content_soup.body.unwrap()

        # process <blockquote>
        for match in post_content_soup.findAll('blockquote'):
            mf = match.findAll(recursive=False)
            match.contents = [m for m in match.contents if m != '\n']
            for k, v in enumerate(mf):
                if isinstance(v, Tag) and v.name != 'p' and v.name != 'br':
                    new_p_tag = post_content_soup.new_tag('p')
                    new_p_tag.string = v.text
                    match.contents[k] = new_p_tag

            if len(mf) == 0:
                new_p_tag = post_content_soup.new_tag('p')
                new_p_tag.string = match.text
                match.string = ''
                match.insert(0, new_p_tag)

        # remove span
        for match in post_content_soup.findAll('span'):
            match.replaceWithChildren()

        # remove <a> outside of <img>
        for match in post_content_soup.findAll('img'):
            if isinstance(match.parent, Tag) and match.parent.name == 'a':
                try:
                    if re.match(r'.*\.(jpg|png|gif|bmp)', match.parent['href']).group():
                        match.parent.unwrap()
                except:
                    pass
            #try:
            #    new_br_tag = post_content_soup.new_tag('br')
            #    match.parent.insert(-1, new_br_tag)
            #except:
            #    pass

            #if isinstance(match.parent, Tag) and match.parent.name == 'p':
            #    match.parent['style'] = 'text-align: center;'

        # wrap div outside of table
        for v in post_content_soup.findAll('table'):
            new_div_tag = post_content_soup.new_tag('div', **{'class': 'tableWrap'})
            contents = v.replace_with(new_div_tag)
            new_div_tag.append(contents)

        # wrap div outside of iframe which src is youtube.com/xxx
        for v in post_content_soup.findAll('iframe'):
            if v['src'] is not None and v['src'].find('www.youtube.com') != -1:
                new_div_tag = post_content_soup.new_tag('div', **{'class': 'youtube'})
                contents = v.replace_with(new_div_tag)
                new_div_tag.append(contents)

        # process <!--nextpage-->
        comments = post_content_soup.find_all(string=lambda text:isinstance(text,Comment))
        for comment in comments:
            if comment == 'nextpage':
                pp = comment.parent
                try:
                    ct = 1
                    pps = pp.find_previous_sibling()
                    while True:
                        if ct > 5:
                            break

                        if len(pps.findChildren('a')) > 0:
                            pps.extract()
                            break
                        else:
                            pps = pps.find_previous_sibling()
                            ct += 1

                    pp.unwrap()
                except:
                    pass

        _wp_post['post_content'] = post_content_soup.prettify(indent_width=2)

        # cleanup empty tags
        _wp_post['post_content'] = _wp_post['post_content'].replace('<p>\n  <br/>\n</p>', '')
        _wp_post['post_content'] = _wp_post['post_content'].replace('<p>\n</p>', '')

        # replace <a> tag which values are https://localhost.com/archives/ZZZ
        reps = []
        a_tags = post_content_soup.findAll('a')
        for a_tag in a_tags:
            try:
                matches = re.search(r'^https:\/\/localhost.com\/archives', a_tag['href'])
                if matches is not None:
                    reps.append(a_tag['href'])
            except:
                pass

        # replace absolute link into relative.
        for rep in reps:
            r = rep.split('https://localhost.com/archives')[1]
            _wp_post['post_content'] = _wp_post['post_content'].replace(rep, '/archives' + r)

        # XXX: fix [nextpage] format error
        if _wp_post['ID'] in fix_nextpage_dicts.keys():
            for tp in fix_nextpage_dicts[_wp_post['ID']]:
                _wp_post['post_content'] = _wp_post['post_content'].replace(*tp)

        # unescape html
        _wp_post['post_content'] = h.unescape(_wp_post['post_content'])

        # trim html tags
        _content = post_content_soup.text

        # validate meta key
        for k in ['_aioseop_keywords', '_aioseop_description', '_aioseop_title', 'subtitle']:
            if k not in _wp_post['meta']:
                _wp_post['meta'][k] = ''

        _wp_post['post_content'] = _wp_post['post_content'].replace('https://localhost.com/wp-content/uploads/', 'https://stg.localhost/640/480/uploads/')

        _post = {
            'id': _wp_post['ID'],
            'operator_id': 0, # TODO:
            'author_id': _wp_post['post_author'],
            'editor_id': 1,
            'category_id': 0,
            'image_id': 1,
            'company_id': 0,
            'title': _wp_post['post_title'],
            'content': _content,
            'lead_content': _content[:140],
            'html_content': _wp_post['post_content'],
            'sub_title': _wp_post['meta']['subtitle'],
            'meta_description': _wp_post['meta']['_aioseop_description'],
            'meta_keywords': _wp_post['meta']['_aioseop_keywords'],
            'meta_title': _wp_post['meta']['_aioseop_title'],
            'noindex_flg': False,
            'nofollow_flg': False,
            'nolist_flg': False,
            'ogp_image_config': 1,
            'twitter_card': 2,
            'amp_flg': False,
            'instant_articles_flg': False,
            'status': 1,
            'trash_flg': False,
            'created_at': _wp_post['post_date'],
            'updated_at': _wp_post['post_modified'],
            'image_urls': [],
            'related_article_ids': _wp_post['related_article_ids'],
            'related_article_titles': _wp_post['related_article_titles'],
            #'image_urls': [img['src'] for img in post_content_soup.findAll('img') if 'src' in img],
        }

        for img in post_content_soup.findAll('img'):
            try:
                isrc = img['src']
                _post['image_urls'].append(isrc)
            except:
                pass

        if 'wplink' in _wp_post:
            _post['wplink'] = _wp_post['wplink']

        if _wp_post['post_status'] == 'publish' or _wp_post['post_status'] == 'future':
            _post['published_at'] = _wp_post['post_date']

        # change to features when import
        if 'series' in _wp_post['meta'] and _wp_post['meta']['series'] != "":
            _post['series_id'] = _wp_post['meta']['series']
        else:
            # query =>  select * from wp_term_relationships where term_taxonomy_id = 774;
            se = xs(cursor, feature_ids)
            if se is not None:
                _post['series_id'] = se['term_taxonomy_id']
            else:
                _post['series_id'] = 0

        ctrls = []
        try:
            ctrls = phpserialize.loads(_wp_post['meta']['pr']).values()
        except:
            pass

        _post['is_pr'] = '588' in ctrls
        _post['is_hide'] = '587' in ctrls

        if _post['is_hide']:
            _post['nolist_flg'] = True

        try:
            if _wp_post['meta']['_aioseop_noindex'] == 'on':
                _post['noindex_flg'] = True
        except:
            pass

        try:
            if _wp_post['meta']['_aioseop_nofollow'] == 'on':
                _post['nofollow_flg'] = True
        except:
            pass

        ## START add categories relations into post
        sql = "SELECT * FROM wp_term_relationships where object_id = {}".format(_wp_post['ID'])
        cursor.execute(sql)
        wp_term_relationships_result = cursor.fetchall()
        for wtr in wp_term_relationships_result:
            if wtr['term_taxonomy_id'] in cat_dict:
                _post['category_id'] = cat_dict[wtr['term_taxonomy_id']]['term_id']
                break
        ## END

        ## START add tags relations into post
        _post['tag_ids'] = []
        is_fisco = False
        for wtr in wp_term_relationships_result:
            if wtr['term_taxonomy_id'] in post_tag_dict:
                # check if article is Fisco
                if post_tag_dict[wtr['term_taxonomy_id']]['term_id'] == 541:
                    is_fisco = True

                _post['tag_ids'].append(post_tag_dict[wtr['term_taxonomy_id']]['term_id'])
                _pid = post_tag_dict[wtr['term_taxonomy_id']]['parent']
                while _pid != 0:
                    if _pid not in post_tag_dict:
                        break

                    _post['tag_ids'].append(post_tag_dict[_pid]['term_id'])
                    _pid = post_tag_dict[_pid]['parent']

        # Don't import Fisco articles
        if not is_fisco:
            wp_post_lists.append(_post)

    return wp_post_lists
