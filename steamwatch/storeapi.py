#-*- coding: utf-8 -*-
# pylint: disable=logging-format-interpolation
'''
Steam store HTTP API

**Endpoints:**

- :func:`appdetails`
- :func:`packagedetails`

.. note::

    Although parameters are name ``appids``/``packageids`` (plural),
    it is only possible to retrieve data for a single entity(?)
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


def appdetails(appid, country_code=None):
    '''Get details for a single steamapp.

    This is a HTTP request to::

        GET http://store.steampowered.com/api/appdetails/?appids=12345

    :param str appid:
        The appid.
    param str country_code:
        The country for which to fetch details.
        Important for currency and country-specific prices/offers.
    :returns:
        A dict with appdetails.
    :rtype: dict
    '''
    params = {'appids': appid}
    if country_code:
        params.update(cc=country_code)
    url = '{base}/appdetails?{query}'.format(
        base=BASEURL,
        query=urlencode(params)
    )
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


def packagedetails(packageid, country_code=None):
    '''Get details for a single package.

    This is a HTTP request to::

        GET http://store.steampowered.com/api/packagedetails/?packageids=12345

    :param str appid:
        The package id.
    param str country_code:
        The country for which to fetch details.
        Important for currency and country-specific prices/offers.
    :returns:
        A dict with package details.
    :rtype: dict
    '''
    params = {'packageids': packageid}
    if country_code:
        params.update(cc=country_code)
    url = '{base}/packagedetails?{query}'.format(
        base=BASEURL,
        query=urlencode(params)
    )
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
    # TODO proper error handling - or none
    try:
        response = urlopen(url)
    except HTTPError:
        raise
    except ContentTooShortError:
        raise
    except URLError:
        raise
    except Exception:
        raise

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
