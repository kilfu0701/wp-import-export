import os
import json
import re
from datetime import date, datetime
from bs4 import BeautifulSoup
import phpserialize
import pymysql.cursors


class DBConn:
    def __init__(self, config={}):
        self.config = config or self._use_default_config()
        self.conn = pymysql.connect(**self.config)
        self.cursor = self.conn.cursor()

    def get_cursor(self):
        return self.cursor

    def close(self):
        self.conn.close()

    def _use_default_config(self):
        return {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'db': 'wordpress',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
        }
