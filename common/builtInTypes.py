import sys
from . import util

types = set([
    'string', 'bool',
    'float', 'int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64',
])

stringValuedTypes = set([ 'string' ])
typesQuotedOnlyInJSON = set([])
memAllocatedTypes = set([ 'string' ])

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
}

def typeCheck(val, ty):
    _typeCheckFuncs[ty](val)
