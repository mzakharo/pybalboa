""" Nothing to see here """
import sys

__version__ = "0.13"

__uri__ = 'https://github.com/garbled1/pybalboa'
__title__ = "pybalboa"
__description__ = 'Interface Library for Balboa Spa'
__doc__ = __description__ + " <" + __uri__ + ">"
__author__ = 'Tim Rightnour, Nathan Spencer'
__email__ = 'root@garbled.net'
__license__ = "Apache 2.0"

__copyright__ = "Copyright (c) 2019 Tim Rightnour"

from .balboa import *

if __name__ == '__main__': print(__version__)
