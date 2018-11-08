import pymysql

config = {
    'dev': {
        'db': {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'db': 'wordpress',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
        },
        'url': {
            'user': 'https://localhost',
            'admin': 'https://admin.localhost',
        },
        'account': {
            'email': 'kilfu0701@example.com',
            'password': 'p@ssw0rd',
        },
        'path': {
            'tmp_image': '/tmp'
        },
    },


    'stage': {
        'db': {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'db': 'wordpress',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
        },
        'url': {
            'user': 'https://stg.localhost',
            'admin': 'https://stg-admin.localhost',
        },
        'account': {
            'email': 'kilfu0701@example.com',
            'password': 'p@ssw0rd',
        },
        'path': {
            'tmp_image': '/tmp'
        },
    },


    'prod': {
        'db': {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'db': 'wordpress',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
        },
        'url': {
            'user': 'https://prd.localhost',
            'admin': 'https://prd-admin.localhost',
        },
        'account': {
            'email': 'kilfu0701@example.com',
            'password': 'p@ssw0rd',
        },
        'path': {
            'tmp_image': '/tmp'
        },
    }
}
