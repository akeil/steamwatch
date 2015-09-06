#-*- coding: utf-8 -*-
'''
Exceptions for steamwatch.

'''


class ConfigurationError(Exception):
    pass


# not used in the template - delete if not required.
class ApplicationError(Exception):
    '''Base class for errors in the application logic.'''
    pass


class GameNotFoundError(ApplicationError):
    pass
