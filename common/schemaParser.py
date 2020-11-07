import sys, json
from external.jsmin import jsmin
from . import util, builtInTypes

STRUCT_LINK_TO_SUPER = '%%super'
STRUCT_ABSTRACT = '%%abstract'

# normal value(field) descriptor keys
NVDK_DESC = '%desc'
NVDK_TYPE = '%type'
NVDK_DEFAULT = '%default'
NVDK_SAMPLE = '%sample'
NVDK_SETTABLE = '%settable'
normFieldDescKeys = set([ NVDK_DESC, NVDK_TYPE, NVDK_DEFAULT, NVDK_SAMPLE, NVDK_SETTABLE ])

reservedFlds = set(['_config_file_path_', '_revision_', 'ERROR'])

def registerEnumDef(enumDefs, enumName, enumBody):
    #print(enumName)
    if not isinstance(enumBody, list):
        raise Exception('enum must be an array, which is not for ' + enumName)

    if len(enumBody) == 0:
        raise Exception('enum must be a non-emptyt array, which is not for ' + enumName)

    for i in enumDefs:
        if i[0] == enumName:
            raise Exception('enum ' + enumName + ' has already been defined')

    for i in enumBody:
        if not util.isString(i):
            raise Exception('enum must be an array of strings, which is not for ' + enumName)

    #print('registering enum ' + enumName)
    enumDefs.append([enumName, enumBody])

def registerStructDef(structName, structBody, enumDefs, structDefs, arrElemTypes, superName, abstract):
    #print(structName)
    if not isinstance(structBody, dict):
        raise Exception('struct body must be an object, which is not for ' + structName)

    for i in structDefs:
        if i[0] == structName:
            raise Exception('strcut ' + strcutName + ' has already been defined')

    structDesc = parseStruct(structBody, enumDefs, structDefs, arrElemTypes, structName)

    if superName:
        structDesc[STRUCT_LINK_TO_SUPER] = superName
    if abstract:
        structDesc[STRUCT_ABSTRACT] = True;

    #print('registering struct ' + structName)
    structDefs.append([structName, structDesc])

def isDefinedType(tyName, definedList):
    for pair in definedList:
        if tyName == pair[0]:
            return True
    return False

def getArrayElementType(arrDesc, enumDefs, structDefs, arrElemTypes, scope):
    if len(arrDesc) != 1:
        raise Exception('array field descriptor must have exactly one element, which is not for ' + str(arrDesc))

    elmtDesc = arrDesc[0]

    if isinstance(elmtDesc, dict):
        registerStructDef(scope, elmtDesc, enumDefs, structDefs, arrElemTypes, None, False)
        return scope
    elif util.isString(elmtDesc):
        return elmtDesc
    else:
        raise Exception('array field descriptor must have a string or object element, which is not for ' + str(arrDesc))

def normalizeFieldDescriptor(fldName, fldDesc, enumDefs, structDefs, arrElemTypes, scope):

    # field descriptor must be a JSON object
    if not isinstance(fldDesc, dict):
        raise Exception('field descriptor must be a JSON Object, which is not for ' + str(fldDesc))

    # mandatory fields of field descriptors
    if not (NVDK_TYPE in fldDesc):
        raise Exception('field descriptor must have a ' + NVDK_TYPE + ' field, which is not for ' + str(fldDesc))

    # does the field descriptor have illegal fields?
    keys = set(fldDesc.keys())
    diff = keys - normFieldDescKeys
    if len(diff) > 0:
        raise Exception('field descriptor has invalid keys: ' + str(diff))

    result = {}

    # description
    if NVDK_DESC in fldDesc:
        desc = fldDesc[NVDK_DESC]
        if desc == None or util.isString(desc):
            if desc == None or len(desc.strip()) == 0:
                result[NVDK_DESC] = '...'
            else:
                result[NVDK_DESC] = desc
        else:
            raise Exception('invalid field description ' + str(desc))
    else:
        result[NVDK_DESC] = '...'


    # type
    ty = fldDesc[NVDK_TYPE]
    if isinstance(ty, dict):
        implicitStructName = scope + '__' + fldName
        registerStructDef(implicitStructName, ty, enumDefs, structDefs, arrElemTypes, None, False)
        result[NVDK_TYPE] = implicitStructName
    elif isinstance(ty, list):
        arrElemType = getArrayElementType(ty, enumDefs, structDefs, arrElemTypes, scope + '__' + fldName + '_elem')
        arrElemTypes.append(arrElemType)
        result[NVDK_TYPE] = [ arrElemType ]
    elif util.isString(ty):
        result[NVDK_TYPE] = ty
    else:
        raise Exception('invalid field type ' + str(ty))

    # default value
    if NVDK_DEFAULT in fldDesc:
        result[NVDK_DEFAULT] = fldDesc[NVDK_DEFAULT]

    # sample value to use in the generated config file sample
    if NVDK_SAMPLE in fldDesc:
        result[NVDK_SAMPLE] = fldDesc[NVDK_SAMPLE]

    # settable
    if NVDK_SETTABLE in fldDesc:
        if isinstance(fldDesc[NVDK_SETTABLE], bool):
            result[NVDK_SETTABLE] = fldDesc[NVDK_SETTABLE]
        else:
            raise Exception('value of "' + NVDK_SETTABLE + '" must be boolean, which is not for ' +
                    str(fldDesc[NVDK_SETTABLE]))
    else:
        result[NVDK_SETTABLE] = False

    return result

def parseStruct(schema, enumDefs, structDefs, arrElemTypes, scope):
    if not isinstance(schema, dict):
        raise Exception('given schema is not a JSON object')

    result = {}

    for key in schema.keys():
        if key != key.strip():
            raise Exception('key "' + key + '" starts or ends with a whitespace')

        if key.startswith('%enum '):
            # enum definition
            split = key.split()
            if len(split) != 2:
                raise Exception('enum definition must be of the form "%enum <enum-name>", which is not for "' +
                        key + '"')
            enumName = split[1]
            # check if enum name is a valid C identifier or not
            util.checkIfIdIsValid(enumName)
            registerEnumDef(enumDefs, enumName, schema[key])
        elif key.startswith('%struct '):
            # struct definition
            split = key.split()

            # check if structure name is a valid C identifier or not
            structName = split[1]
            util.checkIfIdIsValid(structName)

            if len(split) == 2:
                registerStructDef(structName, schema[key], enumDefs, structDefs, arrElemTypes, None, False)
            elif len(split) == 3 and split[2] == 'abstract':
                registerStructDef(structName, schema[key], enumDefs, structDefs, arrElemTypes, None, True)
            elif len(split) == 4 and split[2] == 'extends':
                registerStructDef(structName, schema[key], enumDefs, structDefs, arrElemTypes, split[3], False)
            else:
                raise Exception('struct definition must be of the form "%struct <struct-name>", ' +
                    'which is not for "' + key + '"')
        else:
            # field declaration
            #print(key + ': ' + str(schema[key]))

            if key in reservedFlds:
                raise Exception(key + ' cannot be a field name because it is internally used');

            # check if key is a valid C identifier or not
            util.checkIfIdIsValid(key)
            fldDescriptor = normalizeFieldDescriptor(key, schema[key], enumDefs, structDefs, arrElemTypes, scope)
            result[key] = fldDescriptor

    return result

def checkIfDeclaredType(enumDefs, structDefs, ty):
    return (ty in builtInTypes.types) or (ty in enumDefs) or (ty in structDefs)

def typeCheckValue(enumDefs, structDefs, val, ty):
    if isinstance(ty, list):
        assert len(ty) == 1 and util.isString(ty[0])

        elemTy = ty[0]
        checkIfDeclaredType(enumDefs, structDefs, elemTy)

        if val == None:
            pass # null is OK for arrays
        else:
            if isinstance(val, list):
                for elem in val:
                    typeCheckValue(enumDefs, structDefs, elem, elemTy)
            else:
                raise Exception('value of an array field must be null or an array, which is not for ' + str(val))
    else:
        assert util.isString(ty)

        checkIfDeclaredType(enumDefs, structDefs, ty)

        if ty in builtInTypes.types:
            builtInTypes.typeCheck(val, ty)
        elif ty in enumDefs:
            if not (util.isString(val) and (val in set(enumDefs[ty]))):
                raise Exception(str(val) + ' is not a valid item of enum ' + ty)
        elif ty in structDefs:
            if val == None:
                pass    # null is OK for struct type
            elif isinstance(val, dict):
                structDesc = structDefs[ty]
                structDescKeys = structDesc.keys()

                # keys of val must be a subset of keys of struct desc
                keyDiff = set(val.keys()) - set(structDescKeys)
                if len(keyDiff) > 0:
                    raise Exception(str(val) + ' has fields ' + str(keyDiff) + ' which are undeclared in type ' + ty)

                # val must have a field whose default value is not defined
                for k in structDescKeys:
                    kDesc = structDesc[k]
                    if (not (NVDK_DEFAULT in kDesc)) and (not (k in val)):
                        raise Exception('value ' + str(val) + ' must have field ' + k + ' because its type ' + ty +
                                ' does not define a default value of ' + k)

                # check into the field recursively
                for k, v in val.items():
                    typeCheckValue(enumDefs, structDefs, v, structDesc[k][NVDK_TYPE])
            else:
                raise Exception('value of a struct field must be null or a struct, which is not for ' + str(val))
        else:
            assert False, ('unreachable: ty = ' + str(ty))

def typeCheckFieldValues(enumDefs, structDefs, structDesc):
    for fldName, fldDesc in structDesc.items():
        ty = fldDesc[NVDK_TYPE]
        assert ty
        if isinstance(ty, list):
            assert len(ty) == 1 and util.isString(ty[0])
            elemTy = ty[0]
            checkIfDeclaredType(enumDefs, structDefs, elemTy)
        else:
            assert util.isString(ty)
            checkIfDeclaredType(enumDefs, structDefs, ty)

        # check default value
        if NVDK_DEFAULT in fldDesc:
            typeCheckValue(enumDefs, structDefs, fldDesc[NVDK_DEFAULT], ty)

        # check sample value
        if NVDK_SAMPLE in fldDesc:
            typeCheckValue(enumDefs, structDefs, fldDesc[NVDK_SAMPLE], ty)

def parse(schemaName, schemaFilePaths):
    enumDefs = []
    structDefs = []
    arrElemTypes = []
    schema = {}
    for p in schemaFilePaths:
        print('merging ' + p + ' into schema ' + schemaName)
        minified = jsmin(open(p, 'rb').read().decode('utf-8'))
        partial = json.loads(minified)

        for k, v in partial.items():
            if k in schema:
                raise Exception('key ' + k + ' appears second time in ' + p)
            schema[k] = v

    registerStructDef(schemaName, schema, enumDefs, structDefs, arrElemTypes, None, False)
    print('parsed schema ' + schemaName)
    enumDefs = dict(enumDefs)
    structDefs = dict(structDefs)
    arrElemTypes = set(arrElemTypes)

    # replace link to super in struct descriptors with the super's field descriptors
    for k, v in structDefs.items():
        if STRUCT_LINK_TO_SUPER in v:
            superName = v[STRUCT_LINK_TO_SUPER]
            del v[STRUCT_LINK_TO_SUPER]
            if superName in structDefs:
                superDesc = structDefs[superName]
                for k2, v2 in superDesc.items():
                    if not k2.startswith('%%'):
                        if k2 in v:
                            raise Exception('struct ' + k + ' has a field that is also declared in its super')
                        else:
                            v[k2] = v2
            else:
                raise Exception('struct ' + k + ' extends undefined ' + superName)

    # remove definitions of abstract structures
    abstractStruct = []
    for k, v in structDefs.items():
        if STRUCT_ABSTRACT in v:
            abstractStruct.append(k)
    for k in abstractStruct:
        del structDefs[k]

    enumTypes = set(enumDefs.keys())
    structTypes = set(structDefs.keys())
    cap = builtInTypes.types & enumTypes
    if len(cap) > 0:
        raise Exception('some enums have names of built-in types: ' + str(cap))
    cap = builtInTypes.types & structTypes
    if len(cap) > 0:
        raise Exception('some structs have names of built-in types: ' + str(cap))
    cap = enumTypes & structTypes
    if len(cap) > 0:
        raise Exception('some names are declared as both an enum and a struct: ' + str(cap))

    for _, structDesc in structDefs.items():
        typeCheckFieldValues(enumDefs, structDefs, structDesc)
    print('typechecked schema ' + schemaName)

    return (enumDefs, structDefs, arrElemTypes)
