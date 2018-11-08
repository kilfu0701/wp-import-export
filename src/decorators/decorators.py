import sys
import re
from bs4 import BeautifulSoup

class extend_bs4_prettify(object):
    def __init__(self, f):
        self.f = f

    def __call__(self, *args):
        orig_prettify = BeautifulSoup.prettify
        r = re.compile(r'^(\s*)', re.MULTILINE)
        def prettify(self, encoding=None, formatter="minimal", indent_width=4):
            return r.sub(r'\1' * indent_width, orig_prettify(self, encoding, formatter))

        BeautifulSoup.prettify = prettify

        r = self.f(*args)
        return r

def set_recursion_limit(param):
    def wrapper(f):
        sys.setrecursionlimit(param)
        return f

    return wrapper
