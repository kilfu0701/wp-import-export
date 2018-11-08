# -*- coding: utf8 -*-
from bs4 import BeautifulSoup

def replacement(wp_user_lists):
    result = []

    for wp_user in wp_user_lists:
        user_bio = BeautifulSoup(wp_user['meta']['user_bio'], "html.parser").text if 'user_bio' in wp_user['meta'] else ''

        role_id = 3
        if wp_user['meta']['wp_user_level'] == "10":
            role_id = 1 # admin
        elif wp_user['meta']['wp_user_level'] == "7" or wp_user['meta']['wp_user_level'] == "2":
            role_id = 2 # editor

        d = {
            'id': wp_user['ID'],
            'email': wp_user['user_email'],
            #'password': wp_user['user_pass'],
            'password': u'hashed_pwd_here',
            'role_id': role_id,
            'image_id': 1,
            'first_name': wp_user['meta']['first_name'] or ' ',
            'last_name': wp_user['meta']['last_name'] or ' ',
            'display_name': wp_user['display_name'] or ' ',
            'profile': user_bio,
            'website': wp_user['user_url'],
            'title': '',
            'trash_flg': False,
            'created_at': wp_user['user_registered'],
            'slug': str(wp_user['ID']),
            #'updated_at': ,
        }

        result.append(d)

    return result
