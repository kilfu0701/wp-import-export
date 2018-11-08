## query shorten url mappings
def get_shorten_urls(cursor):
    cursor.execute("SELECT * FROM wp_options WHERE option_name LIKE 'options_link_short_codes_%';")
    shorten_url_dict = {}
    result = cursor.fetchall()
    for name, text, link in zip(result[0::4], result[1::4], result[2::4]):
        shorten_url_dict[name['option_value']] = {
            'title': text['option_value'],
            'link': link['option_value']
        }

    return shorten_url_dict


def get_wp_terms(cursor):
    cursor.execute("SELECT * FROM wp_terms")
    wp_term_result = cursor.fetchall()
    wp_term_dict = {}
    for term in wp_term_result:
        # XXX: force replacement
        term['name'] = term['name'].split('【')[0]
        wp_term_dict[term['term_id']] = term

    return wp_term_dict


def get_wp_categories(cursor, wp_term_dict={}):
    wp_term_dict = wp_term_dict or get_wp_terms()

    cursor.execute("SELECT * FROM wp_term_taxonomy WHERE taxonomy = 'category'")
    wp_term_taxonomy_result = cursor.fetchall()
    cat_dict = {}
    cat_results = []

    # pickup avaliable items for showing in toolbar
    # level-1
    avaliable_lists = ['investment', 'market', 'wealth-management', 'property', 'business-economy', 'career', 'executive-life']

    # level-2
    """
        var r = {};
        $('.menu-item-object-category').each((k,v) => {
          $(v).find('a').each((a, b) => {
            var z = $(b).attr('href').split('/').slice(-1)[0];
            r[z] = 1;
          });
        });
        console.log(Object.keys(r));
    """
    level2 = [
        "investment-start", "investment-basic", "investment-column",
        "wp-news", "market-outlook", "market-analysis", "feature-yutai",
        "money-value", "loan", "money-prepare", "succession", "money-save",
        "realestate-trade", "realestate-investment", "overseas-real-estate",
        "japan", "china-korea", "europe-usa", "world", "feature-fintech",
        "career-workplace", "career-change", "career-education", "career-global",
        "life-culture", "people", "health-care"
    ]
    avaliable_lists = avaliable_lists + level2

    for cat in wp_term_taxonomy_result:
        cat_dict[cat['term_taxonomy_id']] = cat
        _cat = {
            'id': cat['term_id'],
            'name': wp_term_dict[cat['term_id']]['name'],
            'slug': wp_term_dict[cat['term_id']]['slug'],
            'parent': cat['parent'],
        }

        if _cat['slug'] in avaliable_lists:
            _cat['display_flg'] = True
        else:
            _cat['display_flg'] = False

        cat_results.append(_cat)

    return (cat_dict, cat_results)


def get_wp_tags(cursor, wp_term_dict={}):
    wp_term_dict = wp_term_dict or get_wp_terms()

    cursor.execute("SELECT * FROM wp_term_taxonomy WHERE taxonomy = 'post_tag'")
    pt_result = cursor.fetchall()
    post_tag_dict = {}
    post_tag_results = []
    for pt in pt_result:
        post_tag_dict[pt['term_taxonomy_id']] = pt
        _pt = {
            'id': pt['term_taxonomy_id'],
            'name': wp_term_dict[pt['term_id']]['name'],
            'slug': wp_term_dict[pt['term_id']]['slug'],
            'parent': pt['parent'],
        }
        post_tag_results.append(_pt)

    return (post_tag_dict, post_tag_results)


def get_wp_users(cursor):
    cursor.execute("SELECT * FROM wp_users")
    wp_user_result = cursor.fetchall()
    wp_user_dict = {}
    for wp_user in wp_user_result:
        wp_user_dict[wp_user['ID']] = wp_user
        wp_user_dict[wp_user['ID']]['meta'] = {}

    cursor.execute("SELECT * FROM wp_usermeta")
    wp_usermeta_result = cursor.fetchall()

    for wp_usermeta in wp_usermeta_result:
        wp_user_dict[wp_usermeta['user_id']]['meta'][wp_usermeta['meta_key']] = wp_usermeta['meta_value']

    wp_user_lists = []
    for k in wp_user_dict:
        wp_user_lists.append(wp_user_dict[k])

    return (wp_user_dict, wp_user_lists)


def get_wp_posts_count(cursor):
    cursor.execute("SELECT COUNT(*) AS count FROM wp_posts WHERE post_type = 'post'")
    return cursor.fetchone()['count']


def get_wp_posts(cursor, per=100, page=1):
    cursor.execute("SELECT * FROM wp_posts WHERE post_type = 'post' ORDER BY ID ASC LIMIT %s, %s", ((page - 1) * per, per))
    return cursor.fetchall()

def get_all_wp_posts(cursor):
    cursor.execute("SELECT ID, post_content FROM wp_posts WHERE post_type = 'post' ORDER BY ID ASC")
    return cursor.fetchall()

def get_wp_metadata_by_post_id(cursor, post_id):
    cursor.execute("SELECT * FROM wp_postmeta WHERE post_id = %s", post_id)
    return cursor.fetchall()

def get_all_s3_images_url(cursor):
    cursor.execute("SELECT post_id, meta_value FROM wp_postmeta WHERE meta_key = '_s3_media_files-replace'")
    return cursor.fetchall()

def get_thumb_image_by_post(cursor, post_id):
    cursor.execute("SELECT guid FROM wp_posts WHERE ID = (SELECT meta_value FROM wp_postmeta WHERE meta_key = '_thumbnail_id' AND post_id = %s)", post_id)
    return cursor.fetchone()

def get_sponsors(cursor):
    cursor.execute("SELECT * FROM wp_termmeta WHERE meta_key = 'wp_category_ad'")
    return cursor.fetchall()

def get_features(cursor):
    cursor.execute("SELECT B.* FROM wp_terms AS B INNER JOIN wp_term_taxonomy AS A ON B.term_id = A.term_id WHERE A.taxonomy = 'series'")
    return cursor.fetchall()

def xs(cursor, ids):
    cursor.execute("SELECT * FROM wp_term_relationships WHERE term_taxonomy_id IN (%s) LIMIT 1" % ', '.join(map(lambda x: '%s', ids)), ids)
    return cursor.fetchone()

def check_if_fisco(cursor, post_id):
    cursor.execute("SELECT COUNT(*) AS c FROM wp_term_relationships where object_id = %s and term_taxonomy_id = 541;", str(post_id))
    if cursor.fetchone()['c'] == 0:
        return False
    else:
        return True
