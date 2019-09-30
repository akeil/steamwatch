#-*- coding: utf-8 -*-
'''
Utility functions for steamwatch
'''
import re


_MATCHERS = (
    re.compile('^\s*([0-9]+)\s*$'),
    re.compile('^.*?store\.steampowered\.com/app/([0-9]+).*?$'),
)

def extract_appid(text):
    '''Extract the steam app id from the given text.

    Can deal with the following input:

    - appid, e.g. 677340 (is returned as is)
    - store-url, e.g. https://store.steampowered.com/app/677340/The_Colonists/
    '''
    if not text:
        raise ValueError('Invalid App ID %s' % text)

    normalized = text.lower().strip()
    appid = None
    for expr in _MATCHERS:
        match = expr.search(normalized)
        if match:
            appid = match.group(1)
            break

    if not appid:
        raise ValueError('Invalid App ID %s' % text)

    try:
        return '%s' % int(appid)  # "0123" => "123"
    except ValueError:
        # rewrite the error message
        raise ValueError('Invalid App ID %s' % text)
