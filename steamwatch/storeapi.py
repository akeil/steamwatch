#-*- coding: utf-8 -*-
'''
Steam store HTTP API

Methods
#######

appdetails
==========

::

    GET http://store.steampowered.com/api/appdetails/?appids={APPIDS}

:appids:
    a comma-separated list of *appids*, e.g. ``1230,10050``.

'''
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError
from urllib.error import HTTPError
from urllib.error import ContentTooShortError
import json
import logging

from steamwatch.exceptions import GameNotFoundError


BASEURL = 'http://store.steampowered.com/api'
log = logging.getLogger(__name__)


def appdetails(appid):
    '''Get details for a single steamapp.

    :param int appid:
        the appid
    :returns object:
        appdetails
    '''
    query = urlencode({'appids': appid})
    url = '{base}/appdetails?{query}'.format(base=BASEURL, query=query)
    response = _get(url)
    result = _readjson(response)

    try:
        success = result[appid]['success']
    except KeyError:
        success = False

    if not success:
        raise GameNotFoundError
    else:
        return result[appid]['data']


def packagedetails(packageid):
    query = urlencode({'packageids': packageid})
    url = '{base}/packagedetails?{query}'.format(base=BASEURL, query=query)
    response = _get(url)
    result = _readjson(response)

    try:
        success = result[packageid]['success']
    except KeyError:
        success = False

    if not success:
        raise GameNotFoundError
    else:
        return result[packageid]['data']


def _get(url):
    log.debug('GET {u!r}'.format(u=url))
    # TODO proper error handling
    try:
        response = urlopen(url)
    except HTTPError as e:
        raise e
    except ContentTooShortError as e:
        raise
    except URLError as e:
        log.exception(e)
        raise e
    except Exception as e:
        raise e

    log.debug('{} {}'.format(response.status, response.reason))

    if response.status not in (200,):
        raise ValueError('{} {}'.format(response.status, response.reason))

    return response


def _readjson(response):
    encoding = 'utf-8'  # default
    contenttype = response.getheader('Content-Type')
    log.debug('Content-Type: {!r}'.format(contenttype))
    if contenttype:
        try:
            # expected: application/json; charset=utf-8
            encoding = contenttype.split(';')[1].split('=')[1].strip().lower()
        except IndexError:
            pass  # not found

    return json.loads(response.read().decode(encoding))
