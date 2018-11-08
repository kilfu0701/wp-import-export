# -*- coding: utf8 -*-
import sys

"""
    ref: https://github.com/kilfu0701/py_tools/blob/master/debug/debug.py

    @Usage:
        import Debug as D
        d = D(level=4, color=True)
        d.info('Some info', my_vars)
        d.log('This is Log')
        d.debug('For debugging')
        d.error('Fatal Errors', error_objects)
    @param:
        level: integer.
        color: boolean.
    @def:
        info(..)
        log(..)
        debug(..)
        error(..)
    @author:
        kilfu0701 (kilfu0701@gmail.com)
"""
class Debug(object):
    def __init__(self, level=4, color=False, types='unicode'):
        self.color = color
        self.level = level
        self.types = types

        self._pv = {
            'info': {
                'level': 4,
                'color': ByColors.OKGREEN,
            },
            'log': {
                'level': 3,
                'color': ByColors.HEADER,
            },
            'debug': {
                'level': 2,
                'color': ByColors.WARNING,
            },
            'error': {
                'level': 1,
                'color': ByColors.FAIL,
            },
        }

    def info(self, msg='', *args, **kwargs):
        self._pr(sys._getframe().f_code.co_name, msg, *args)

    def log(self, msg='', *args, **kwargs):
        self._pr(sys._getframe().f_code.co_name, msg, *args)

    def debug(self, msg='', *args, **kwargs):
        self._pr(sys._getframe().f_code.co_name, msg, *args)

    def error(self, msg='', *args, **kwargs):
        self._pr(sys._getframe().f_code.co_name, msg, *args)

    def _pr(self, func, msg, *args):
        if self.level >= self._pv[func]['level']:
            if self.color:
                func_txt = self._pv[func]['color'] + func.upper() + ByColors.ENDC
            else:
                func_txt = func.upper()

            if self.types == 'repr':
                print "[{0}]\t{1} {2}".format(func_txt, repr(msg), ' '.join(map(repr, args)))
            else:
                print u"[{0}]\t{1} {2}".format(func_txt, unicode(msg), ' '.join(map(unicode, args)))


class ByColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
