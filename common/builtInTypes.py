import sys
from . import util

types = set([
    'string', 'bool',
    'float', 'int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64',
    'IP', 'MAC', 'CIDR', 'IP_Range', 'IP_Port',
])

stringValuedTypes = set([ 'string', 'IP', 'MAC', 'CIDR', 'IP_Range', 'IP_Port' ])
typesQuotedOnlyInJSON = set(['IP', 'MAC', 'CIDR', 'IP_Range', 'IP_Port' ])
memAllocatedTypes = set(['string', 'IP', 'MAC', 'CIDR', 'IP_Range', 'IP_Port' ])

def _typeCheckString(val):
    if not (val == None or util.isString(val)):
        raise Exception(str(val) + ' is not of the declared type string')

def _typeCheckBool(val):
    if not isinstance(val, bool):
        raise Exception(str(val) + ' is not of the declared type bool')

def _typeCheckFloat(val):
    if not isinstance(val, float):
        raise Exception(str(val) + ' is not of the declared type float')

def _hexStrToLong(s):
    if s.startswith('0x'):
        return long(s, 16)
    else:
        raise Exception('string literals for an integer field must start with "0x": ' + s)

def _typeCheckInt(val, bits):
    if util.isString(val):
        val2 = _hexStrToLong(val)
    else:
        val2 = val

    if isinstance(val2, int) or isinstance(val2, long):
        bound = 1 << (bits - 1)
        if (val2 < -bound) or (val2 >= bound):
            raise Exception('value ' + str(val) + ' is out of valid range of the declared type int' + str(bits))
    else:
        raise Exception(str(val) + ' is not of an integer type')

def _typeCheckUint(val, bits):
    if util.isString(val):
        val2 = _hexStrToLong(val)
    else:
        val2 = val

    if isinstance(val2, int) or isinstance(val2, long):
        if (val2 < 0) or (val2 >= (1 << bits)):
            raise Exception('value ' + str(val) + ' is out of valid range of the declared type uint' + str(bits))
    else:
        raise Exception(str(val) + ' is not of an integer type')

def _typeCheckInt8(val):
    _typeCheckInt(val, 8)

def _typeCheckInt16(val):
    _typeCheckInt(val, 16)

def _typeCheckInt32(val):
    _typeCheckInt(val, 32)

def _typeCheckInt64(val):
    _typeCheckInt(val, 64)

def _typeCheckUint8(val):
    _typeCheckUint(val, 8)

def _typeCheckUint16(val):
    _typeCheckUint(val, 16)

def _typeCheckUint32(val):
    _typeCheckUint(val, 32)

def _typeCheckUint64(val):
    _typeCheckUint(val, 64)

def _typeCheckIP(val):
    if not util.isString(val):
        raise Exception('IP values must be strings: ' + str(val))

    if val.find(' ') >= 0:
        raise Exception('IP values may not have a blank: "' + val + '"')

    splitted = val.split('.')
    if len(splitted) != 4:
        raise Exception('IP values must have four segments delimited by dots: ' + val)

    for s in splitted:
        try:
            i = int(s)
        except ValueError:
            raise Exception(val + ' is not a valid IP address')

        if i < 0 or i > 255:
            raise Exception('Each segment in an IP value must be an unsigned 8-bit integer: ' + str(i) + ' in ' + val)

def _typeCheckMAC(val):
    if not util.isString(val):
        raise Exception('MAC values must be strings: ' + str(val))

    if val.find(' ') >= 0:
        raise Exception('MAC values may not have a blank: "' + val + '"')

    splitted = val.split(':')
    if len(splitted) != 6:
        raise Exception('MAC values must have six segments delimited by colons: ' + val)

    for s in splitted:
        if len(s) != 2:
            raise Exception('Each segment in a MAC value must be a string of length 2: ' + s + ' in ' + val)

        try:
            i = int(s, 16)
        except ValueError:
            raise Exception(val + ' is not a valid MAC address')

        if i < 0 or i > 255:
            raise Exception('Each segment in a MAC value must be an unsigned 8-bit integer: ' + str(i) + ' in ' + val)

def _typeCheckCIDR(val):
    if not util.isString(val):
        raise Exception('CIDR values must be strings: ' + str(val))

    if val.find(' ') >= 0:
        raise Exception('CIDR values may not have a blank: "' + val + '"')

    splitted = val.split('/')
    if len(splitted) != 2:
        raise Exception('CIDR values must have two components, an IP and a mask length, delimited by a slash: ' + val)

    _typeCheckIP(splitted[0])

    maskLen = int(splitted[1])
    if maskLen < 0 or maskLen > 32:
        raise Exception('A CIDR value must have a mask length less than or equal to 32: ' + val)

def _typeCheckIP_Range(val):
    if not util.isString(val):
        raise Exception('IP_Range values must be strings: ' + str(val))

    if val.find(' ') >= 0:
        raise Exception('IP_Range values may not have a blank: "' + val + '"')

    splitted = val.split('~')
    if len(splitted) == 1:
        _typeCheckIP(splitted[0])
    elif len(splitted) == 2:
        _typeCheckIP(splitted[0])
        _typeCheckIP(splitted[1])
        first = map(lambda x: int(x), splitted[0].split('.'))
        last = map(lambda x: int(x), splitted[1].split('.'))
        if first >= last:
            raise Exception('the first IP must be less than the last IP in IP Range values: ' + val)
    else:
        raise Exception('A illegal format of an IP Range value: ' + val)

def _typeCheckIP_Port(val):
    if not util.isString(val):
        raise Exception('IP_Port values must be strings: ' + str(val))

    if val.find(' ') >= 0:
        raise Exception('IP_Port values may not have a blank: "' + val + '"')

    splitted = val.split(':')
    if len(splitted) != 2:
        raise Exception('IP_Port values must have two components, an IP and a port, delimited by a colon: ' + val)

    _typeCheckIP(splitted[0])

    port = int(splitted[1])
    if port < 0 or port > 65535:
        raise Exception('port is not in the valid ranges of ports: ' + val)

_typeCheckFuncs = {
    'string': _typeCheckString,
    'bool': _typeCheckBool,

    'float': _typeCheckFloat,

    'int8': _typeCheckInt8,
    'int16': _typeCheckInt16,
    'int32': _typeCheckInt32,
    'int64': _typeCheckInt64,
    'uint8': _typeCheckUint8,
    'uint16': _typeCheckUint16,
    'uint32': _typeCheckUint32,
    'uint64': _typeCheckUint64,

    'IP': _typeCheckIP,
    'MAC': _typeCheckMAC,
    'CIDR': _typeCheckCIDR,
    'IP_Range': _typeCheckIP_Range,
    'IP_Port': _typeCheckIP_Port,
}

def typeCheck(val, ty):
    _typeCheckFuncs[ty](val)
