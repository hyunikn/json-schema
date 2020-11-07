import os
import sys
import json

from common import util, schemaParser, builtInTypes, sampleGenerator
from . import misc

_builtInTypeToJavaTypeMap = {
    'string': 'String',
    'bool': 'boolean',

    'float': 'double',
    'int8': 'byte',
    'int16': 'short',
    'int32': 'int',
    'int64': 'long',
    'uint8': 'short',
    'uint16': 'int',
    'uint32': 'long',
    'uint64': 'UINT64',

    'IP': 'IPv4Address',
    'MAC': 'MacAddress',
    'CIDR': 'IPv4AddressWithMask',
    'IP_Range': 'IpRange',
    'IP_Port': 'IpPort',
}
assert set(_builtInTypeToJavaTypeMap.keys()) == builtInTypes.types, 'every built-in type must have its Java-type'

# ------Write Interface-----------------------------------------------------

_tmplEnumDef = '''
%OPT-PUBLIC%enum %ENUM-TYPE% {
%ENUM-ITEMS%
}
'''

_tmplInnerIntfDef = '''
interface %INTERFACE-TYPE% {
%FIELD-ACCESSORS%
}
'''

_tmplIntfDef = '''
public interface %INTERFACE-TYPE% {

    // field getters
%FIELD-ACCESSORS%

    //
    String getSchema();

    // enum definitions
%ENUM-DEFS%

    // inner interface definitions
%NESTED-INTERFACE-DEFS%
}
'''

def _schemaTypeToJavaType(sType, enumDef, structDef, forIntf):
    if isinstance(sType, list):
        return _schemaTypeToJavaType(sType[0], enumDef, structDef, forIntf) + '[]'
    elif sType in _builtInTypeToJavaTypeMap:
        return _builtInTypeToJavaTypeMap[sType]
    elif sType in enumDef:
        return misc.getTypeName(sType)
    elif sType in structDef:
        if forIntf:
            return misc.getIntfName(sType)
        else:
            return misc.getClasName(sType)

    assert false, 'unreachable: undefined type in the schema'

def _getFldJavaType(fldDesc, enumDef, structDef, forIntf):
    fldType = fldDesc[schemaParser.NVDK_TYPE]
    if isinstance(fldType, list):
        elemType = fldType[0]
        fldJavaType = _schemaTypeToJavaType(elemType, enumDef, structDef, forIntf) + '[]'
    else:
        fldJavaType = _schemaTypeToJavaType(fldType, enumDef, structDef, forIntf)

    return fldJavaType

def _getInnerIntfDef(name, desc, enumDef, structDef):
    intfType = misc.getIntfName(name)

    # get field accessors
    fldAccessors = []
    structDesc = structDef[name]
    for fld, desc in structDesc.items():
        fldJavaType = _getFldJavaType(desc, enumDef, structDef, True)
        fldAccessors.append(fldJavaType + ' ' + fld + '();')

    return (_tmplInnerIntfDef
                .replace('%INTERFACE-TYPE%', intfType)
                .replace('%FIELD-ACCESSORS%', util.indent('\n'.join(fldAccessors), 1)))

def _getEnumDefStrList(enumDef, forInterface):
    enumDefStrList = []
    for name, body in enumDef.items():
        enumType = misc.getTypeName(name)
        enumDefStrList.append(_tmplEnumDef
                                  .replace('%OPT-PUBLIC%', ("" if forInterface else "public "))
                                  .replace('%ENUM-TYPE%', enumType)
                                  .replace('%ENUM-ITEMS%', util.indent(',\n'.join(body), 1)))
    return enumDefStrList

# ------Write Implementation-----------------------------------------------------

_tmplParseEnum = '''\
(%VAL% instanceof String) ? %TY%.valueOf((String) %VAL%) : (%TY%) JsonSchema.throwAsExpr("enum value must be a string")\
'''
_tmplParseStruct = '''JSONObject.NULL.equals(%VAL%) ? null : new %TY%((JSONObject) %VAL%)'''

def _getParseValTmpl(valType, enumDef, structDef):
    if isinstance(valType, list):
        parseVal = 'parseArr_%TY%(%VAL%)'.replace('%TY%', valType[0])
    elif valType in builtInTypes.types:
        parseVal = 'JsonSchema.parseJSON%TY%(%VAL%)'.replace('%TY%', valType)
    elif valType in enumDef:
        enumJavaType = misc.getTypeName(valType)
        parseVal = _tmplParseEnum.replace('%TY%', enumJavaType)
    elif valType in structDef:
        structJavaType = misc.getClasName(valType)
        parseVal = _tmplParseStruct.replace('%TY%', structJavaType)

    return parseVal

# -------------------------------------------------------------------------------

_tmplAssignParsedFieldVal = '%FIELD-JAVA-NAME% = %PARSE-FIELD-VAL%;'

def _getAssignParsedFldStatements(fldName, fldType, enumDef, structDef):
    parseFld = _getParseValTmpl(fldType, enumDef, structDef).replace('%VAL%', 'fld')
    return (_tmplAssignParsedFieldVal
                .replace('%FIELD-JAVA-NAME%', fldName)
                .replace('%PARSE-FIELD-VAL%', parseFld))

# -------------------------------------------------------------------------------

_tmplParseFieldDefaultedTopLevel = '''
if (json.has("%FIELD-NAME%")) {
    fld = json.get("%FIELD-NAME%");
    %FIELD-NAME%__uses_default = false;
} else {
    fld = structDesc.getJSONObject("%FIELD-NAME%").get(NVDK_DEFAULT);
    %FIELD-NAME%__uses_default = true;
}
%SET-FIELD-VAL%\
'''

_tmplParseFieldDefaultedInner = '''
if (json.has("%FIELD-NAME%")) {
    fld = json.get("%FIELD-NAME%");
} else {
    fld = structDesc.getJSONObject("%FIELD-NAME%").get(NVDK_DEFAULT);
}
%SET-FIELD-VAL%\
'''

_tmplParseFieldUndefaulted = '''
if (json.has("%FIELD-NAME%")) {
    fld = json.get("%FIELD-NAME%");
} else {
   throw new Error("field '%FIELD-NAME%' has no default value in the schema and is not set in the JSON file");
}
%SET-FIELD-VAL%\
'''

# get declarations, field accessor defs and statements to set fields
def _getFieldRelatedCode(structDesc, enumDef, structDef, genIntf, isTopLevel):
    fldDecls = []
    fldAccessors = []
    parseFields = []
    fldAccModifier = ('protected ' if genIntf else 'public ')
    for fldName, fldDesc in structDesc.items():
        fldImplType = _getFldJavaType(fldDesc, enumDef, structDef, False)
        fldVar = fldName
        fldDecls.append(fldAccModifier + fldImplType + ' '  + fldVar + ';')
        if isTopLevel and (schemaParser.NVDK_DEFAULT in fldDesc):
            fldDecls.append('private boolean ' + fldName + '__uses_default;')

        if genIntf:
            fldIntfType = _getFldJavaType(fldDesc, enumDef, structDef, True)
            fldAccessors.append('public ' + fldIntfType + ' ' + fldVar + '() { return ' + fldVar + '; }')

        if schemaParser.NVDK_DEFAULT in fldDesc:
            if isTopLevel:
                tmplParseField = _tmplParseFieldDefaultedTopLevel
            else:
                tmplParseField = _tmplParseFieldDefaultedInner
        else:
            tmplParseField = _tmplParseFieldUndefaulted

        assignParsedFieldVal = _getAssignParsedFldStatements(fldName, fldDesc[schemaParser.NVDK_TYPE],
                enumDef, structDef)
        parseFields.append(tmplParseField
                               .replace('%SET-FIELD-VAL%', assignParsedFieldVal)
                               .replace('%FIELD-NAME%', fldName))

    return (fldDecls, fldAccessors, parseFields)

# -------------------------------------------------------------------------------------------------

_tmplPPrintArrCall = '''pprintArr_%TY%(%VAL%, %INDENT%, sbuf, mode, contentMask, %KEY-TAIL%, errMsg);'''
_tmplPPrintStructCall = '''%TY%.pprintNullable(%VAL%, %INDENT%, sbuf, mode, contentMask, %KEY-TAIL%, errMsg);'''
_tmplPPrintNotQuotableBuiltInTypeCall = '''JsonSchema.pprint_%TY%(%VAL%, sbuf);'''
_tmplPPrintQuotableBuiltInTypeCall = '''if (mode == JsonSchema.PrintMode.JSON) { JsonSchema.bprint(sbuf, "\\""); JsonSchema.pprint_%TY%(%VAL%, sbuf); JsonSchema.bprint(sbuf, "\\""); } else { JsonSchema.pprint_%TY%(%VAL%, sbuf); }'''
_tmplPPrintEnumTypeCall = '''\
JsonSchema.bprint(sbuf, mode == JsonSchema.PrintMode.JSON ? "\\"" + %VAL%.name() + "\\"" : %VAL%.name());'''

_tmplSelectAndRecurseIntoNextFld = '''\
if (keyHead.equals("%FIELD-NAME%")) {
    %RECURSE-INTO-NEXT-FLD%;
}\
'''

_tmplPPrintLeafFld = '''\
if (keyHead.equals("%FIELD-NAME%")) {
    if (keyTail == null) {
        %PPRINT-LEAF-FLD%;
    } else {
        JsonSchema.bprint(errMsg, "[Error] no such key '" + keyTail + "' in the JSON file");
    }
}\
'''

def _getPPrintNextStmts(fld, ty, enumDef, structDef):
    if isinstance(ty, list) or (ty in structDef):

        if isinstance(ty, list):
            tmplPPrintCall = _tmplPPrintArrCall.replace('%TY%', ty[0])
        else:
            classType = misc.getClasName(ty)
            tmplPPrintCall = _tmplPPrintStructCall.replace('%TY%', classType)

        pprintCall = (tmplPPrintCall
                          .replace('%INDENT%', '0')
                          .replace('%KEY-TAIL%', 'keyTail'))

        return (_tmplSelectAndRecurseIntoNextFld
                    .replace('%RECURSE-INTO-NEXT-FLD%', pprintCall)
                    .replace('%VAL%', fld)
                    .replace('%FIELD-NAME%', fld))
    else:
        if (ty in builtInTypes.types):

            if (ty in builtInTypes.typesQuotedOnlyInJSON):
                tmplPPrintCall = _tmplPPrintQuotableBuiltInTypeCall
            else:
                tmplPPrintCall = _tmplPPrintNotQuotableBuiltInTypeCall

            pprintCall = tmplPPrintCall.replace('%TY%', ty)

        elif (ty in enumDef):
            pprintCall = _tmplPPrintEnumTypeCall
        else:
            assert False

        return (_tmplPPrintLeafFld
                    .replace('%PPRINT-LEAF-FLD%', pprintCall)
                    .replace('%VAL%', fld)
                    .replace('%FIELD-NAME%', fld))

# ----------------------------------------------------------------------------------------------------

_tmplPrintComment = '''\
    if ((contentMask & JsonSchema.TOP_LEVEL_COMMENT) != 0) {
        String fldComment = fldComments.getString("%FIELD-NAME%");
        assert fldComment != null;
        JsonSchema.bprint(sbuf, "\\n");
        JsonSchema.bprint(sbuf, fldComment.replaceAll("\\\\n", "\\n"));
        JsonSchema.bprint(sbuf, "\\n");
    }
'''

_strNewLine = '''\
    JsonSchema.bprint(sbuf, mode == JsonSchema.PrintMode.JSON ? ",\\n": "\\n");
'''

_tmplPlainFldPPrintStmts = '''
// %FIELD-NAME%
//if ((contentMask) != 0) {     TODO: implement filtering
%OPT-NEW-LINE%\
%OPT-PRINT-COMMENT%\
    JsonSchema.printIndent(indent + 1, sbuf);
    if (mode == JsonSchema.PrintMode.JSON) {
        JsonSchema.bprint(sbuf, "\\"%FIELD-NAME%\\": ");
    } else {
        JsonSchema.bprint(sbuf, "%FIELD-NAME%: ");
    }
    %PPRINT-CALL%
//}
'''

_tmplDefaultedTopLevelFldPPrintStmts = '''
// %FIELD-NAME%
//if ((contentMask) != 0) {     TODO: implement filtering
%OPT-NEW-LINE%\
%OPT-PRINT-COMMENT%\
    JsonSchema.printIndent(indent + 1, sbuf);
    if ((contentMask & JsonSchema.DEFAULT_COMMENT) != 0 && %FIELD-NAME%__uses_default) {
        JsonSchema.bprint(sbuf, "//");
    }
    if (mode == JsonSchema.PrintMode.JSON) {
        JsonSchema.bprint(sbuf, "\\"%FIELD-NAME%\\": ");
    } else {
        JsonSchema.bprint(sbuf, "%FIELD-NAME%: ");
    }
    if ((contentMask & JsonSchema.DEFAULT_COMMENT) != 0 && %FIELD-NAME%__uses_default) {
        JsonSchema.bprint(sbuf, "%default");
    } else {
        %PPRINT-CALL%
    }
//}
'''

def _getPPrintFldStmts(i, fld, ty, enumDef, structDef, writeComment, isDefaultedTopLevel):

    if isinstance(ty, list):
        pprintCall = (_tmplPPrintArrCall
                          .replace('%TY%', ty[0])
                          .replace('%INDENT%', 'indent + 1')
                          .replace('%KEY-TAIL%', 'null'))
    elif ty in builtInTypes.types:
        if ty in builtInTypes.typesQuotedOnlyInJSON:
            tmplPPrintBuiltInTypeCall = _tmplPPrintQuotableBuiltInTypeCall
        else:
            tmplPPrintBuiltInTypeCall = _tmplPPrintNotQuotableBuiltInTypeCall

        pprintCall = tmplPPrintBuiltInTypeCall.replace('%TY%', ty)
    elif ty in enumDef:
        pprintCall = _tmplPPrintEnumTypeCall
    elif ty in structDef:
        classType = misc.getClasName(ty)
        pprintCall = (_tmplPPrintStructCall
                          .replace('%TY%', classType)
                          .replace('%INDENT%', 'indent + 1')
                          .replace('%KEY-TAIL%', 'null'))

    tmplFldPPrintStmts = _tmplDefaultedTopLevelFldPPrintStmts if isDefaultedTopLevel else _tmplPlainFldPPrintStmts

    return (tmplFldPPrintStmts
                .replace('%OPT-NEW-LINE%', _strNewLine if i > 0 else '')
                .replace('%OPT-PRINT-COMMENT%', _tmplPrintComment if writeComment else '')
                .replace('%PPRINT-CALL%', pprintCall)
                .replace('%VAL%', fld)
                .replace('%FIELD-NAME%', fld))

# -------------------------------------------------------------------------------------------

_tmplUnsetDefaultFlag = '''
    %FLD%__uses_default = false;\
'''

_tmplUpdateFld = '''\
if (keyHead.equals("%FLD%")) {
    %FLD-JAVA-TYPE% newVal;
    try {
        newVal = %PARSE-NEW-VAL%;
    } catch (Throwable e) {
        errMsg.append("[Error] given new value is not assignable to the value at the key: " + e.getMessage());
        return JsonSchema.SetErr.ERR_INCOMPATIBLE_VAL;
    }

    if (checkOnly) {
        onVal[0] = newVal;
        return JsonSchema.SetErr.OK;
    } else {
        onVal[0] = %FLD-JAVA-NAME%;
    }

    %FLD-JAVA-NAME% = newVal;
%OPT-UNSET-DEFAULT-FLAG%
    return JsonSchema.SetErr.OK;
}\
'''

def _getUpdateFld(fld, fldType, fldDefaulted, enumDef, structDef, isTopLevel):
    parseNewVal = _getParseValTmpl(fldType, enumDef, structDef).replace('%VAL%', 'newValJSON')

    if fldDefaulted and isTopLevel:
        tmpl = _tmplUpdateFld.replace('%OPT-UNSET-DEFAULT-FLAG%', _tmplUnsetDefaultFlag)
    else:
        tmpl = _tmplUpdateFld.replace('%OPT-UNSET-DEFAULT-FLAG%', '')

    return (tmpl.replace('%FLD-JAVA-TYPE%', _schemaTypeToJavaType(fldType, enumDef, structDef, False))
                .replace('%PARSE-NEW-VAL%', parseNewVal)
                .replace('%FLD-JAVA-NAME%', fld)
                .replace('%FLD%', fld))

# ---------------------------------------------------------------------------------------------------------


_tmplInsertArrElem = '''\
if (keyHead.equals("%FLD%")) {
    %ELEM-JAVA-TYPE% newVal;
    final int IDX_MAX = %FLD-JAVA-NAME% == null ? 0 : %FLD-JAVA-NAME%.length;

    if (idx == -1) {
        // insert at the end
        idx = IDX_MAX;
    }

    if (idx < 0 || idx > IDX_MAX) {
        errMsg.append("[Error] array index " + idx + " is out of range for the current length of array " + keyHead);
        return JsonSchema.SetErr.ERR_INDEX_OUT_OF_RANGE;
    }

    try {
        newVal = %PARSE-NEW-VAL%;
    } catch (Throwable e) {
        errMsg.append("[Error] given new value cannot be inserted into the array at the key");
        return JsonSchema.SetErr.ERR_INCOMPATIBLE_VAL;
    }

    if (checkOnly) {
        onVal[0] = newVal;
        return JsonSchema.SetErr.OK;
    } else {
        onVal[0] = (idx == IDX_MAX ? null : %FLD-JAVA-NAME%[idx]);
    }

    {
        int i;
        %ELEM-JAVA-TYPE%[] newArr = new %ELEM-JAVA-TYPE%[IDX_MAX + 1];

        for (i = 0; i < idx; i++) {
            newArr[i] = %FLD-JAVA-NAME%[i];
        }
        newArr[idx] = newVal;
        for (i = idx; i < IDX_MAX; i++) {
            newArr[i + 1] = %FLD-JAVA-NAME%[i];
        }

        %FLD-JAVA-NAME% = newArr;
    }
%OPT-UNSET-DEFAULT-FLAG%
    return JsonSchema.SetErr.OK;
}\
'''

def _getInsertArrElem(fld, fldType, fldDefaulted, enumDef, structDef, isTopLevel):
    assert isinstance(fldType, list)
    elemType = fldType[0]

    parseNewVal = _getParseValTmpl(elemType, enumDef, structDef).replace('%VAL%', 'newValJSON')

    if fldDefaulted and isTopLevel:
        tmpl = _tmplInsertArrElem.replace('%OPT-UNSET-DEFAULT-FLAG%', _tmplUnsetDefaultFlag)
    else:
        tmpl = _tmplInsertArrElem.replace('%OPT-UNSET-DEFAULT-FLAG%', '')

    return (tmpl.replace('%ELEM-JAVA-TYPE%', _schemaTypeToJavaType(elemType, enumDef, structDef, False))
                .replace('%PARSE-NEW-VAL%', parseNewVal)
                .replace('%FLD-JAVA-NAME%', fld)
                .replace('%FLD%', fld))


# ---------------------------------------------------------------------------------------------------------

_tmplRemoveArrElem = '''\
if (keyHead.equals("%FLD%")) {
    int IDX_MAX;
    if (%FLD-JAVA-NAME% != null && %FLD-JAVA-NAME%.length > 0) {
        IDX_MAX = %FLD-JAVA-NAME%.length - 1;
    } else {
        errMsg.append("[Error] cannot remove the last element of a null or empty array " + keyHead);
        return JsonSchema.SetErr.ERR_EMPTY_ARRAY;
    }

    if (idx == -1) {
        // remove at the end
        idx = IDX_MAX;
    }

    if (idx < 0 || idx > IDX_MAX) {
        errMsg.append("[Error] array index " + idx + " is out of range for the current length of the array " + keyHead);
        return JsonSchema.SetErr.ERR_INDEX_OUT_OF_RANGE;
    }

    if (checkOnly) {
        onVal[0] = null;
        return JsonSchema.SetErr.OK;
    } else {
        onVal[0] = %FLD-JAVA-NAME%[idx];
    }

    {
        int i;
        %ELEM-JAVA-TYPE%[] newArr = new %ELEM-JAVA-TYPE%[IDX_MAX];

        for (i = 0; i < idx; i++) {
            newArr[i] = %FLD-JAVA-NAME%[i];
        }
        for (i = idx; i < IDX_MAX; i++) {
            newArr[i] = %FLD-JAVA-NAME%[i + 1];
        }

        %FLD-JAVA-NAME% = newArr;
    }
%OPT-UNSET-DEFAULT-FLAG%
    return JsonSchema.SetErr.OK;
}\
'''

def _getRemoveArrElem(fld, fldType, fldDefaulted, enumDef, structDef, isTopLevel):
    assert isinstance(fldType, list)
    elemType = fldType[0]

    if fldDefaulted and isTopLevel:
        tmpl = _tmplRemoveArrElem.replace('%OPT-UNSET-DEFAULT-FLAG%', _tmplUnsetDefaultFlag)
    else:
        tmpl = _tmplRemoveArrElem.replace('%OPT-UNSET-DEFAULT-FLAG%', '')

    return (tmpl.replace('%ELEM-JAVA-TYPE%', _schemaTypeToJavaType(elemType, enumDef, structDef, False))
                .replace('%FLD-JAVA-NAME%', fld)
                .replace('%FLD%', fld))

# ---------------------------------------------------------------------------------------------------------

_tmplRecurseSetArrWithDefaultFlag = '''\
if (keyHead.equals("%FLD%")) {
    JsonSchema.SetErr recRes = setArr_%FLD-TYPE%(mode, %FLD-JAVA-NAME%, %IS-ARR-SETTABLE%, keyTail, idx, newValJSON, checkOnly, onVal, errMsg);
    if (!checkOnly && (recRes == JsonSchema.SetErr.OK)) {
        %FLD%__uses_default = false;
    }
    return recRes;
}\
'''

_tmplRecurseSetNonArrWithDefaultFlag = '''\
if (keyHead.equals("%FLD%")) {
    JsonSchema.SetErr recRes = %CLASS-TYPE%.setNullable(%FLD-JAVA-NAME%, mode, keyTail, idx, newValJSON, checkOnly, onVal, errMsg);
    if (!checkOnly && (recRes == JsonSchema.SetErr.OK)) {
        %FLD%__uses_default = false;
    }
    return recRes;
}\
'''

_tmplRecurseSetArr = '''\
if (keyHead.equals("%FLD%")) {
    return setArr_%FLD-TYPE%(mode, %FLD-JAVA-NAME%, %IS-ARR-SETTABLE%, keyTail, idx, newValJSON, checkOnly, onVal, errMsg);
}\
'''

_tmplRecurseSetNonArr = '''\
if (keyHead.equals("%FLD%")) {
    return %CLASS-TYPE%.setNullable(%FLD-JAVA-NAME%, mode, keyTail, idx, newValJSON, checkOnly, onVal, errMsg);
}\
'''

def _getRecurseSet(fld, fldType, fldSettable, fldDefaulted, enumDef, structDef, isTopLevel):
    if isinstance(fldType, list):
        if fldDefaulted and isTopLevel:
            tmpl = _tmplRecurseSetArrWithDefaultFlag
        else:
            tmpl = _tmplRecurseSetArr
        return (tmpl.replace('%FLD%', fld)
                    .replace('%FLD-JAVA-NAME%', fld)
                    .replace('%FLD-TYPE%', fldType[0])
                    .replace('%IS-ARR-SETTABLE%', 'true' if fldSettable else 'false'))
    elif fldType in structDef:
        if fldDefaulted and isTopLevel:
            tmpl = _tmplRecurseSetNonArrWithDefaultFlag
        else:
            tmpl = _tmplRecurseSetNonArr
        return (tmpl.replace('%FLD%', fld)
                    .replace('%FLD-JAVA-NAME%', fld)
                    .replace('%CLASS-TYPE%', misc.getClasName(fldType)))
    else:
        assert False

# ---------------------------------------------------------------------------------------------------------

_strStructSetCurrWithoutSettableArrs = '''
        case INSERT:
        case REMOVE:
            if (mode == JsonSchema.SetMode.INSERT) {
                errMsg.append("[Error] unable to insert an element into a non-array field " + keyHead);
            } else {
                errMsg.append("[Error] unable to remove an element from a non-array field " + keyHead);
            }
            return JsonSchema.SetErr.ERR_NOT_AN_ARRAY;\
'''

_tmplStructSetCurrWithSettableArrs = '''
        case INSERT:
            assert idx >= -1;
            assert newValJSON != null;

            if (%IS-NOT-SETTABLE-ARRAY%) {
                errMsg.append("[Error] unable to insert an element into a non-array field " + keyHead);
                return JsonSchema.SetErr.ERR_NOT_AN_ARRAY;
            }
%INSERT-ARR-ELEM%
            assert false;   // unreachable
            break;

        case REMOVE:
            assert idx >= -1;
            assert newValJSON == null;

            if (%IS-NOT-SETTABLE-ARRAY%) {
                errMsg.append("[Error] unable to remove an element from a non-array field " + keyHead);
                return JsonSchema.SetErr.ERR_NOT_AN_ARRAY;
            }
%REMOVE-ARR-ELEM%
            assert false;   // unreachable
            break;\
'''

_strStructSetCurrWithoutSettables = '''
        // this struct has no settable fields at the current level
        errMsg.append("[Error] unable to set field " + keyHead + " which is not settable");
        return JsonSchema.SetErr.ERR_NOT_SETTABLE;\
'''

_tmplStructSetCurrWithSettables = '''
        // keyHead is the field to set

        if (%IS-NOT-SETTABLE%) {
            errMsg.append("[Error] unable to set field " + keyHead + " which is not settable");
            return JsonSchema.SetErr.ERR_NOT_SETTABLE;
        }

        switch (mode) {
        case UPDATE:
            assert idx == -1;
            assert newValJSON != null;
%UPDATE-FIELD%
            assert false;   // unreachable
            break;
%SET-THIS-LEVEL-ARR-FIELDS%

        default:
            assert false;
        }

        assert false;
        return JsonSchema.SetErr.ERR_UNREACHABLE;\
'''

_tmplStructSetDef = '''
private JsonSchema.SetErr set(JsonSchema.SetMode mode, String key, int idx, Json newValJSON, boolean checkOnly, Object[] onVal, StringBuffer errMsg) {

    assert key != null: "key may not be null";

    String keyHead, keyTail;
    int delim = key.indexOf('.');
    if (delim < 0) {
        keyHead = key;
        keyTail = null;
    } else {
        keyHead = key.substring(0, delim);
        keyTail = key.substring(delim + 1);
    }

    if (keyTail == null) {
%SET-THIS-LEVEL-FIELDS%
    } else {
%CHECK-SIMPLE-FLD%
%RECURSE-INTO-NEXT-FLD%
        errMsg.append("[Error] invalid key segment " + keyHead);
        return JsonSchema.SetErr.ERR_NO_SUCH_FIELD;
    }
}
'''

_tmplCheckSimpleFld = '''
if (%IS-SIMPLE-FLD%) {
    errMsg.append("[Error] unable to recurse set into " + keyHead + " which has no substructures");
    return JsonSchema.SetErr.ERR_DEREF_PRIMITIVE;
}\
'''

def _getSetMethodDef(struct, structDesc, enumDef, structDef, isTopLevel):
    assert structDesc != None;

    fields = list(structDesc.keys())
    fields.sort()

    simpleFld = []
    compoundFld = []
    settableFld = []
    settableArrayFld = []
    for fld in fields:
        fldDesc = structDesc[fld]
        fldType = fldDesc[schemaParser.NVDK_TYPE]
        fldSettable = fldDesc[schemaParser.NVDK_SETTABLE]

        if isinstance(fldType, list) or (fldType in structDef):
            compoundFld.append(fld)
        else:
            simpleFld.append(fld)

        if fldSettable:
            settableFld.append(fld)
            if isinstance(fldType, list):
                settableArrayFld.append(fld)

    # checkSimpleFld
    if len(simpleFld) > 0:
        isSimpleFld = ' || '.join(map(lambda fld: 'keyHead.equals("' + fld + '")', simpleFld))
        checkSimpleFld = _tmplCheckSimpleFld.replace('%IS-SIMPLE-FLD%', isSimpleFld)
    else:
        checkSimpleFld = ''

    # recurse
    recurse = []
    for fld in compoundFld:
        fldDesc = structDesc[fld]
        fldType = fldDesc[schemaParser.NVDK_TYPE]
        fldSettable = fldDesc[schemaParser.NVDK_SETTABLE]
        fldDefaulted = (schemaParser.NVDK_DEFAULT in fldDesc)
        recurse.append(_getRecurseSet(fld, fldType, fldSettable, fldDefaulted, enumDef, structDef, isTopLevel))

    tmpl = _tmplStructSetDef
    if len(settableFld) > 0:
        tmpl = tmpl.replace('%SET-THIS-LEVEL-FIELDS%', _tmplStructSetCurrWithSettables)

        # isNotSettable
        isNotSettable = ' && '.join(map(lambda fld: '!keyHead.equals("' + fld + '")', settableFld))

        # update
        update = []
        for fld in settableFld:
            fldDesc = structDesc[fld]
            fldType = fldDesc[schemaParser.NVDK_TYPE]
            fldDefaulted = (schemaParser.NVDK_DEFAULT in fldDesc)
            update.append(_getUpdateFld(fld, fldType, fldDefaulted, enumDef, structDef, isTopLevel))

        tmpl = (tmpl.replace('%IS-NOT-SETTABLE%', isNotSettable)
                    .replace('%UPDATE-FIELD%', util.indent(' else '.join(update), 3)))

        if len(settableArrayFld) > 0:
            tmpl = tmpl.replace('%SET-THIS-LEVEL-ARR-FIELDS%', _tmplStructSetCurrWithSettableArrs)

            # isNotSettableArray
            isNotSettableArray = ' && '.join(map(lambda fld: '!keyHead.equals("' + fld + '")', settableArrayFld))

            # insertArrElem and removeArrElem
            insertArrElem = []
            removeArrElem = []
            for fld in settableArrayFld:
                fldDesc = structDesc[fld]
                fldType = fldDesc[schemaParser.NVDK_TYPE]
                fldDefaulted = (schemaParser.NVDK_DEFAULT in fldDesc)
                insertArrElem.append(_getInsertArrElem(fld, fldType, fldDefaulted, enumDef, structDef, isTopLevel))
                removeArrElem.append(_getRemoveArrElem(fld, fldType, fldDefaulted, enumDef, structDef, isTopLevel))

            tmpl = (tmpl.replace('%IS-NOT-SETTABLE-ARRAY%', isNotSettableArray)
                        .replace('%INSERT-ARR-ELEM%', util.indent(' else '.join(insertArrElem), 3))
                        .replace('%REMOVE-ARR-ELEM%', util.indent(' else '.join(removeArrElem), 3)))

        else:
            tmpl = tmpl.replace('%SET-THIS-LEVEL-ARR-FIELDS%', _strStructSetCurrWithoutSettableArrs)
    else:
        tmpl = tmpl.replace('%SET-THIS-LEVEL-FIELDS%', _strStructSetCurrWithoutSettables)

    return (tmpl.replace('%CHECK-SIMPLE-FLD%', util.indent(checkSimpleFld, 2))
                .replace('%RECURSE-INTO-NEXT-FLD%', util.indent(' else '.join(recurse), 2)))

# -------------------------------------------------------------------------------------------

_tmplParseArrFld = '''
private static %ELEM-JAVA-TYPE%[] parseArr_%ELEM-TYPE%(Object fld) {
    if (JsonObj.NULL.equals(fld)) {
        return null;
    } else if (fld instanceof JSONArray) {
        JSONArray jsonArr = (JSONArray) fld;
        int arrLen = jsonArr.length();
        %ELEM-JAVA-TYPE%[] arr = new %ELEM-JAVA-TYPE%[arrLen];
        for (int k = 0; k < arrLen; k++) {
            Object fldElem = jsonArr.get(k);
            arr[k] = %PARSE-FIELD-VAL%;
        }
        return arr;
    } else {
        throw new Error("JSON value of a %ELEM-TYPE% array type field is neither null nor an array: " + fld.getClass());
    }
}
'''

def _getArrParseDef(elemType, enumDef, structDef):
    #NOTE: elemType cannot be an array type
    parseFld = _getParseValTmpl(elemType, enumDef, structDef).replace('%VAL%', 'fldElem')
    return (_tmplParseArrFld
                .replace('%ELEM-TYPE%', elemType)
                .replace('%ELEM-JAVA-TYPE%', _schemaTypeToJavaType(elemType, enumDef, structDef, False))
                .replace('%PARSE-FIELD-VAL%', parseFld))

_tmplPPrintNonStructElem = '''
if (keyTail == null) {
    %PPRINT-CALL%
} else {
    JsonSchema.bprint(errMsg, "[Error] no such key '" + keyTail + "' in the JSON file");
    return;
}
'''

_tmplPPrintArr = '''
private static void pprintArr_%ELEM-TYPE%(%ELEM-JAVA-TYPE%[] arr, int indent, StringBuffer sbuf,
        JsonSchema.PrintMode mode, int contentMask, String key, StringBuffer errMsg) {
    if (key == null) {
        if (arr == null) {
            JsonSchema.bprint(sbuf, "null");
        } else if (arr.length == 0) {
            JsonSchema.bprint(sbuf, "[ ]");
        } else {
            JsonSchema.bprint(sbuf, "[\\n");
            for (int i = 0; i < arr.length; i++) {
                %ELEM-JAVA-TYPE% elem = arr[i];
                if (i > 0) {
                    JsonSchema.bprint(sbuf, mode == JsonSchema.PrintMode.JSON ? ",\\n": "\\n");
                }
                JsonSchema.printIndent(indent + 1, sbuf);
                %PPRINT-CALL%
            }
            JsonSchema.bprint(sbuf, "\\n");
            JsonSchema.printIndent(indent, sbuf);
            JsonSchema.bprint(sbuf, "]");
        }
    } else {
        int delim, idx;
        String keyHead, keyTail;
        assert indent == 0: "indent must be zero";

        delim = key.indexOf('.');
        if (delim < 0) {
            keyHead = key;
            keyTail = null;
        } else {
            keyHead = key.substring(0, delim);
            keyTail = key.substring(delim + 1);
        }

        try {
            idx = Integer.valueOf(keyHead, 10);
        } catch (NumberFormatException e) {
            JsonSchema.bprint(errMsg, "[Error] invalid array index (not an integer) " + keyHead);
            return;
        }

        if (arr == null) {
            JsonSchema.bprint(errMsg, String.format("[Error] unable to get the element %d of a null array", idx));
            return;
        }

        if (idx >= arr.length) {
            JsonSchema.bprint(errMsg,
                String.format("[Error] invalid array index %d for an array with length %d", idx, arr.length));
            return;
        }

        %ELEM-JAVA-TYPE% elem = arr[idx];
%PPRINT-ARR-ELEM%
    }
}
'''

def _getArrPPrintDef(elemType, enumDef, structDef):
    if elemType in builtInTypes.types:
        if elemType in builtInTypes.typesQuotedOnlyInJSON:
            tmplPPrintBuiltInTypeCall = _tmplPPrintQuotableBuiltInTypeCall
        else:
            tmplPPrintBuiltInTypeCall = _tmplPPrintNotQuotableBuiltInTypeCall

        pprintCall = (tmplPPrintBuiltInTypeCall.replace('%TY%', elemType))
        pprintArrElem = _tmplPPrintNonStructElem
    elif elemType in enumDef:
        pprintCall = _tmplPPrintEnumTypeCall
        pprintArrElem = _tmplPPrintNonStructElem
    elif elemType in structDef:
        classType = misc.getClasName(elemType)
        pprintCall = (_tmplPPrintStructCall
                          .replace('%TY%', classType)
                          .replace('%INDENT%', 'indent + 1')
                          .replace('%KEY-TAIL%', 'null'))
        pprintArrElem = (_tmplPPrintStructCall
                             .replace('%TY%', classType)
                             .replace('%INDENT%', '0')
                             .replace('%KEY-TAIL%', 'keyTail'))

    return (_tmplPPrintArr
                .replace('%ELEM-TYPE%', elemType)
                .replace('%ELEM-JAVA-TYPE%', _schemaTypeToJavaType(elemType, enumDef, structDef, False))
                .replace('%PPRINT-ARR-ELEM%', util.indent(pprintArrElem, 2))
                .replace('%PPRINT-CALL%', pprintCall)
                .replace('%VAL%', 'elem'))



# -------------------------------------------------------------------------------

_tmplUpdateElem = '''\
%ELEM-JAVA-TYPE% newVal;
try {
    newVal = %PARSE-NEW-VAL%;
} catch (Throwable e) {
    errMsg.append("[Error] given new value is not assignable to the value at the key: " + e.getMessage());
    return JsonSchema.SetErr.ERR_INCOMPATIBLE_VAL;
}

if (checkOnly) {
    onVal[0] = newVal;
    return JsonSchema.SetErr.OK;
} else {
    onVal[0] = arr[elemIdx];
}

arr[elemIdx] = newVal;
return JsonSchema.SetErr.OK;\
'''

def _getUpdateElem(elemType, enumDef, structDef):
    assert not isinstance(elemType, list)
    parseNewVal = _getParseValTmpl(elemType, enumDef, structDef).replace('%VAL%', 'newValJSON')
    return _tmplUpdateElem.replace('%PARSE-NEW-VAL%', parseNewVal)

# ---------------------------------------------------------------------------------------------------------

_tmplArrSetDef = '''
private static JsonSchema.SetErr setArr_%ELEM-TYPE%(JsonSchema.SetMode mode, %ELEM-JAVA-TYPE%[] arr, boolean settable, String key, int idx, Json newValJSON, boolean checkOnly, Object[] onVal, StringBuffer errMsg) {
    assert key != null;

    String keyHead, keyTail;
    int delim = key.indexOf('.');
    if (delim < 0) {
        keyHead = key;
        keyTail = null;
    } else {
        keyHead = key.substring(0, delim);
        keyTail = key.substring(delim + 1);
    }

    int elemIdx;
    try {
        elemIdx = Integer.valueOf(keyHead);
    } catch (NumberFormatException e) {
        errMsg.append("[Error] key segment " + keyHead + " must be an integer which is an array element index");
        return JsonSchema.SetErr.ERR_BAD_INDEX;
    }
    if (elemIdx < 0) {
        errMsg.append("[Error] key segment " + keyHead + " must be a non-negative integer " +
            "which is an array element index");
        return JsonSchema.SetErr.ERR_BAD_INDEX;
    }

    if (arr == null) {
        errMsg.append("[Error] unable to set the element " + keyHead + " of a null array");
        return JsonSchema.SetErr.ERR_DEREF_NULL;
    }

    if (elemIdx >= arr.length) {
        errMsg.append("[Error] array index " + keyHead + " is out of range of the array");
        return JsonSchema.SetErr.ERR_INDEX_OUT_OF_RANGE;
    }

    if (keyTail == null) {
        // keyHead is the field to set

        if (settable) {
            switch (mode) {
            case UPDATE:
                assert idx == -1;
                assert newValJSON != null;

%UPDATE-ELEM%

            case INSERT:
            case REMOVE:
                errMsg.append("[Error] cannot insert into or remove from an array element " + keyHead);
                return JsonSchema.SetErr.ERR_NOT_AN_ARRAY;

            default:
                assert false; // unreachable
            }

            assert false;
            return JsonSchema.SetErr.ERR_UNREACHABLE;
        } else {
            errMsg.append("[Error] unable to set the element " + keyHead + " of the array which is not settable");
            return JsonSchema.SetErr.ERR_NOT_SETTABLE;
        }

    } else {
%ERROR-OR-RECURSE-INTO-NEXT-FLD%
    }
}
'''

_tmplDoRecurse = '''\
return %ELEM-JAVA-TYPE%.setNullable(arr[elemIdx], mode, keyTail, idx, newValJSON, checkOnly, onVal, errMsg);\
'''

_tmplRecurseError = '''\
errMsg.append("[Error] cannot recurse set into the array element " + keyHead + " of a simple type " + "%ELEM-TYPE%");
return JsonSchema.SetErr.ERR_DEREF_PRIMITIVE;\
'''

def _getArrSetDef(elemType, enumDef, structDef):
    # array element cannot be of an array type
    assert not isinstance(elemType, list)

    if elemType in structDef:
        errOrRec = _tmplDoRecurse
    else:
        errOrRec = _tmplRecurseError

    updateFld = _getUpdateElem(elemType, enumDef, structDef)

    return (_tmplArrSetDef
               .replace('%ERROR-OR-RECURSE-INTO-NEXT-FLD%', util.indent(errOrRec, 2))
               .replace('%UPDATE-ELEM%', util.indent(updateFld, 4))
               .replace('%ELEM-TYPE%', elemType)
               .replace('%ELEM-JAVA-TYPE%', _schemaTypeToJavaType(elemType, enumDef, structDef, False))
               )

# --------------------------------------------------------------------------------------------------

_strEmptyStructPPrintBody = '''
private void pprint(int indent, StringBuffer sbuf, JsonSchema.PrintMode mode, int contentMask,
        String key, StringBuffer errMsg) {
    if (key == null) {
        JsonSchema.bprint(sbuf, "{ }");
    } else {
        JsonSchema.bprint(errMsg, "[Error] no such key in the JSON file");
    }
}\
'''

_tmplNonEmptyStructPPrintBody = '''
private void pprint(int indent, StringBuffer sbuf, JsonSchema.PrintMode mode, int contentMask,
        String key, StringBuffer errMsg) {
    if (key == null) {
        JsonSchema.bprint(sbuf, "{\\n");
%PPRINT-FIELDS%
%OPT-END-FOR-TOP-LEVEL%
        JsonSchema.bprint(sbuf, "\\n");
        JsonSchema.printIndent(indent, sbuf);
        JsonSchema.bprint(sbuf, "}");
    } else {
        int delim;
        String keyHead, keyTail;
        assert indent == 0: "indent must be zero";

        delim = key.indexOf('.');
        if (delim < 0) {
            keyHead = key;
            keyTail = null;
        } else {
            keyHead = key.substring(0, delim);
            keyTail = key.substring(delim + 1);
        }

        // select and recurse into the next field
%PPRINT-NEXT%
    }
}\
'''

_strPPrintNextElse = '''\
{
    JsonSchema.bprint(errMsg, "[Error] invalid key segment " + keyHead);
}\
'''

_strPrintEnd = '''\
JsonSchema.bprint(sbuf, ",\\n\\n");
JsonSchema.printIndent(indent + 1, sbuf);
JsonSchema.bprint(sbuf, "\\"%end%\\": null");
'''

def _getPPrintMethodDef(structDesc, enumDef, structDef, writeComments, isTopLevel):
    fields = list(structDesc.keys())
    if len(fields) > 0:
        pprintFields = []
        pprintNext = []

        fields.sort();
        i = 0
        for fld in fields:
            fldDesc = structDesc[fld]
            fldType = fldDesc[schemaParser.NVDK_TYPE]
            pprintFields.append(_getPPrintFldStmts(i, fld, fldType, enumDef, structDef,
                        writeComments, (schemaParser.NVDK_DEFAULT in fldDesc) and isTopLevel))
            pprintNext.append(_getPPrintNextStmts(fld, fldDesc[schemaParser.NVDK_TYPE], enumDef, structDef))
            i += 1
        pprintNext.append(_strPPrintNextElse)

        pprintMethod = (_tmplNonEmptyStructPPrintBody
                            .replace('%PPRINT-FIELDS%', util.indent(''.join(pprintFields), 2))
                            .replace('%OPT-END-FOR-TOP-LEVEL%', util.indent(_strPrintEnd, 2) if isTopLevel else '')
                            .replace('%PPRINT-NEXT%', util.indent(' else '.join(pprintNext), 2)))
    else:
        pprintMethod = _strEmptyStructPPrintBody

    return pprintMethod

# --------------------------------------------------------------------------------------------------

_tmplInnerClassDef = '''
%OPT-PUBLIC%static class %CLASS-TYPE%%OPT-IMPLEMENTS% {
%FIELD-ACCESSORS%
%FIELD-DECLS%

    // ==========================
    // Private
    // ==========================

    private static final JsonObj structDesc =
        schemaJSON.getJSONObject("%struct-def").getJSONObject("%STRUCT-NAME%");

    private %CLASS-TYPE%(JsonObj json) {
        Object fld;

        if (structDesc == null) {
            throw new Error("cannot parse the struct descriptor string of %STRUCT-NAME%");
        }

        Set schemaFields = structDesc.keySet();
        Set jsonFields = new TreeSet(json.keySet());
        jsonFields.remove("%end%");   // end marker
        jsonFields.removeAll(schemaFields);
        if (jsonFields.size() > 0) {
            throw new Error("the JSON file has fields undeclared in the schema: " + jsonFields);
        }
%PARSE-FIELDS%
    }

    private static void pprintNullable(%CLASS-TYPE% val, int indent, StringBuffer sbuf, JsonSchema.PrintMode mode,
            int contentMask, String key, StringBuffer errMsg) {

        if (val == null) {
            if (key == null) {
                JsonSchema.bprint(sbuf, "null");
            } else {
                JsonSchema.bprint(errMsg, "[Error] unable to get the field " + key + " of a null JSON object");
            }
        } else {
            val.pprint(indent, sbuf, mode, contentMask, key, errMsg);
        }
    }
%PPRINT-METHOD%

    private static JsonSchema.SetErr setNullable(%CLASS-TYPE% val, JsonSchema.SetMode mode, String key, int idx, Json newValJSON, boolean checkOnly, Object[] onVal, StringBuffer errMsg) {

        if (val == null) {
            assert key != null: "key must be non-null";
            errMsg.append("[Error] unable to set the field " + key + " of a null JSON object");
            return JsonSchema.SetErr.ERR_DEREF_NULL;
        } else {
            return val.set(mode, key, idx, newValJSON, checkOnly, onVal, errMsg);
        }
    }
%SET-METHOD%
}
'''


def _getInnerClassDef(struct, enumDef, structDef, outerIntfType, genIntf):
    if genIntf:
        optPublic = 'public '
        optImplements = ' implements ' + outerIntfType + '.' + misc.getIntfName(struct)
    else:
        optPublic = ''
        optImplements = ''

    clasType = misc.getClasName(struct)
    structDesc = structDef[struct]

    # field related code: decl/accessor/set
    (fldDecls, fldAccessors, parseFields) = _getFieldRelatedCode(structDesc, enumDef, structDef, genIntf, False)
    # pprint method
    pprintMethod = _getPPrintMethodDef(structDesc, enumDef, structDef, False, False)
    # set method
    setMethodDef = _getSetMethodDef(struct, structDesc, enumDef, structDef, False)

    return (_tmplInnerClassDef
                .replace('%OPT-PUBLIC%', optPublic)
                .replace('%CLASS-TYPE%', clasType)
                .replace('%OPT-IMPLEMENTS%', optImplements)
                .replace('%FIELD-ACCESSORS%', util.indent('\n'.join(fldAccessors), 1))
                .replace('%FIELD-DECLS%', util.indent('\n'.join(fldDecls), 1))
                .replace('%STRUCT-NAME%', struct)
                .replace('%PARSE-FIELDS%', util.indent('\n'.join(parseFields), 2))
                .replace('%PPRINT-METHOD%', util.indent(pprintMethod, 1))
                .replace('%SET-METHOD%', util.indent(setMethodDef, 1))
            )

_tmplOptForOutermost = '''
    // CAUTION: the following two lines must go first in this class definition
    private static final String schemaJsonStr = "%SCHEMA-JSON-STR%";
    private static final JsonObj schemaJSON = JsonObj.parse(schemaJsonStr);

    public String getSchema() {
        return schemaJsonStr;
    }

    public void prettyPrint(StringBuffer sbuf, JsonSchema.PrintMode mode, int contentMask, String key) {
        String resStr;
        StringBuffer resBuf, errMsg;

        resBuf = new StringBuffer();
        errMsg = new StringBuffer();
        pprint(0, resBuf, mode, contentMask, key, errMsg);

        if (errMsg.length() > 0) {
            resStr = errMsg.toString();
            JsonSchema.bprint(sbuf, resStr);
        } else {
            resStr = resBuf.toString();
            JsonSchema.bprint(sbuf, _revision_ + ":");
            JsonSchema.bprint(sbuf, resStr);
        }
    }

    public JsonSchema.SetErr update(int targetRev, String key, String newValJsonStr, boolean checkOnly, boolean save,
            Object[] onVal, StringBuffer errMsg) {

        Json jsonVal;
        try {
            jsonVal = Json.parse(newValJsonStr);
        } catch (JSONException e) {
            errMsg.append("given new value string does not conform to the JSON format: " + e.getMessage());
            return JsonSchema.SetErr.ERR_JSON_PARSE;
        }

        if (targetRev > 0 && targetRev != _revision_) {
            errMsg.append("wrong revision");
            return JsonSchema.SetErr.ERR_WRONG_REVISION;
        }

        JsonSchema.SetErr rc = set(JsonSchema.SetMode.UPDATE, key, -1, jsonVal, checkOnly, onVal, errMsg);
        if (rc == JsonSchema.SetErr.OK && !checkOnly) {
            _revision_++;
            if (save) {
                if (!saveToFile(errMsg)) {
                    return JsonSchema.SetErr.ERR_FAILED_TO_SAVE;
                }
            }
        }

        return rc;
    }

    public JsonSchema.SetErr insertArrElem(int targetRev, String key, int idx, String newValJsonStr, boolean checkOnly,
            boolean save, Object[] onVal, StringBuffer errMsg) {

        Json jsonVal;
        try {
            jsonVal = Json.parse(newValJsonStr);
        } catch (JSONException e) {
            errMsg.append("given new value string does not conform to the JSON format: " + e.getMessage());
            return JsonSchema.SetErr.ERR_JSON_PARSE;
        }

        if (targetRev > 0 && targetRev != _revision_) {
            errMsg.append("wrong revision");
            return JsonSchema.SetErr.ERR_WRONG_REVISION;
        }

        JsonSchema.SetErr rc = set(JsonSchema.SetMode.INSERT, key, idx, jsonVal, checkOnly, onVal, errMsg);
        if (rc == JsonSchema.SetErr.OK && !checkOnly) {
            _revision_++;
            if (save) {
                if (!saveToFile(errMsg)) {
                    return JsonSchema.SetErr.ERR_FAILED_TO_SAVE;
                }
            }
        }

        return rc;
    }

    public JsonSchema.SetErr removeArrElem(int targetRev, String key, int idx, boolean checkOnly, boolean save,
            Object[] onVal, StringBuffer errMsg) {

        if (targetRev > 0 && targetRev != _revision_) {
            errMsg.append("wrong revision");
            return JsonSchema.SetErr.ERR_WRONG_REVISION;
        }

        JsonSchema.SetErr rc = set(JsonSchema.SetMode.REMOVE, key, idx, null, checkOnly, onVal, errMsg);
        if (rc == JsonSchema.SetErr.OK && !checkOnly) {
            _revision_++;
            if (save) {
                if (!saveToFile(errMsg)) {
                    return JsonSchema.SetErr.ERR_FAILED_TO_SAVE;
                }
            }
        }

        return rc;
    }

    %OPT-PUBLIC%%CLASS-TYPE%(String jsonFilePath, boolean prettyPrint, boolean rewrite) {
        this(JsonSchema.readAndParseJSON(jsonFilePath, prettyPrint));

        _json_file_path_ = jsonFilePath;
        _revision_ = 1;

        if (prettyPrint) {
            System.out.println("JSON in effect:");
            prettyPrint(null, JsonSchema.PrintMode.PLAIN, JsonSchema.ALL_TAGS, null);
            System.out.println("");
        }

        if (rewrite) {
            StringBuffer errMsg = new StringBuffer();
            if (saveToFile(errMsg)) {
                if (prettyPrint) {
                    System.out.println("JSON written back successfully");
                }
            } else {
                throw new Error("[Error] failed to write back JSON " + jsonFilePath);
            }
        }
    }
'''

_tmplFldComments = '''
private static final String fldCommentsStr = "%CONF-FLD-COMMENTS-STR%";
private static final JsonObj fldComments = new JsonObj(fldCommentsStr);

'''

_tmplOptPrivForOutermost = '''\
%OPT-CONF-FLD-COMMENTS%\
    private String _json_file_path_;
    private int _revision_;

    private boolean saveToFile(StringBuffer errMsgO) {
        boolean ret = false;
        String resStr;
        StringBuffer resBuf, errMsg;

        resBuf = new StringBuffer();
        errMsg = new StringBuffer();
        pprint(0, resBuf, JsonSchema.PrintMode.JSON, JsonSchema.ALL_TAGS | JsonSchema.TOP_LEVEL_COMMENT | JsonSchema.DEFAULT_COMMENT,
                null, errMsg);

        if (errMsg.length() > 0) {
            resStr = errMsg.toString();
            errMsgO.append("[Error] failed to get the JSON string to save: ");
            errMsgO.append(resStr);
        } else {
            resStr = resBuf.toString();
            try {
                File jsonFile = new File(_json_file_path_);
                if (jsonFile.canWrite()) {
                    byte[] bytes = resStr.getBytes("UTF-8");
                    FileOutputStream out = null;
                    try {
                        out = new FileOutputStream(jsonFile);
                        out.write(bytes);
                    } finally {
                        if (out != null) {
                            out.close();
                        }
                    }

                    ret = true;
                } else {
                    errMsgO.append("[Error] the JSON file is not writable");
                }
            } catch (Throwable e) {
                errMsgO.append("[Error] cannot write the JSON to the file: " + e.getMessage());
            }
        }

        return ret;
    }
'''

_tmplTopClassDef = '''
%OPT-PUBLIC%class %CLASS-TYPE%%OPT-IMPLEMENTS% {
%OPT-FOR-OUTERMOST%
%FIELD-ACCESSORS%
%FIELD-DECLS%
%NESTED-CLASSES%\
%ENUM-DEFS%\

    // ==========================
    // Private
    // ==========================

%NVDK-DEFAULT-DEF%\
%OPT-PRIV-FOR-OUTERMOST%\
    private static final JsonObj structDesc =
        schemaJSON.getJSONObject("%struct-def").getJSONObject("%STRUCT-NAME%");

    private %CLASS-TYPE%(JsonObj json) {
        Json fld;

        if (structDesc == null) {
            throw new Error("cannot parse the struct descriptor string of %STRUCT-NAME%");
        }

        Set schemaFields = structDesc.keySet();
        Set jsonFields = new TreeSet(json.keySet());
        jsonFields.remove("%end%");   // end marker
        jsonFields.removeAll(schemaFields);
        if (jsonFields.size() > 0) {
            throw new Error("the JSON file has fields undeclared in the schema: " + jsonFields);
        }
%PARSE-FIELDS%
    }

    private static void pprintNullable(%CLASS-TYPE% val, int indent, StringBuffer sbuf, JsonSchema.PrintMode mode,
            int contentMask, String key, StringBuffer errMsg) {

        if (val == null) {
            if (key == null) {
                JsonSchema.bprint(sbuf, "null");
            } else {
                JsonSchema.bprint(errMsg, "[Error] unable to get the field " + key + " of a JSON null");
            }
        } else {
            val.pprint(indent, sbuf, mode, contentMask, key, errMsg);
        }
    }
%PPRINT-METHOD%

    private static JsonSchema.SetErr setNullable(%CLASS-TYPE% val, JsonSchema.SetMode mode, String key, int idx, Json newValJSON, boolean checkOnly, Object[] onVal, StringBuffer errMsg) {

        if (val == null) {
            assert key != null: "key must be non-null";
            errMsg.append("[Error] unable to set the field " + key + " of a JSON null");
            return JsonSchema.SetErr.ERR_DEREF_NULL;
        } else {
            return val.set(mode, key, idx, newValJSON, checkOnly, onVal, errMsg);
        }
    }
%SET-METHOD%
%ARRAY-METHODS%\
}
'''

def _getInnerClassDefs(outerStruct, enumDef, structDef, intfType, genIntf):
    innerClasses = []
    for struct in structDef:
        if (struct != outerStruct):
            innerClasses.append(_getInnerClassDef(struct, enumDef, structDef, intfType, genIntf))

    if len(innerClasses) > 0:
        return util.indent(''.join(innerClasses), 1)
    else:
        return ''

def _getArrayMethodDefs(arrElemTypes, enumDef, structDef):
    arrMethodDefs = []
    for elemType in arrElemTypes:
        arrMethodDefs.append(_getArrParseDef(elemType, enumDef, structDef))
        arrMethodDefs.append(_getArrPPrintDef(elemType, enumDef, structDef))
        arrMethodDefs.append(_getArrSetDef(elemType, enumDef, structDef))

    if len(arrMethodDefs) > 0:
        return util.indent('\n// array methods\n' + ''.join(arrMethodDefs), 1)
    else:
        return ''

### Public ###

def writeIntf(intfFile, enumDef, structDef, schemaName):
    intfType = misc.getIntfName(schemaName)

    # get field accessor decls
    fldAccessors = []
    structDesc = structDef[schemaName]
    for fld, desc in structDesc.items():
        fldJavaType = _getFldJavaType(desc, enumDef, structDef, True)
        fldAccessors.append(fldJavaType + ' ' + fld + '();')

    # get enum defs
    enumDefStrs = _getEnumDefStrList(enumDef, True)

    # get inner interface defs corresponding to structs in the schema
    innerIntfDefs = []
    for name, desc in structDef.items():
        if name != schemaName:
            innerIntfDefs.append(_getInnerIntfDef(name, desc, enumDef, structDef))

    intfFile.write(_tmplIntfDef
                       .replace('%INTERFACE-TYPE%', intfType)
                       .replace('%FIELD-ACCESSORS%', util.indent('\n'.join(fldAccessors), 1))
                       .replace('%ENUM-DEFS%', util.indent(''.join(enumDefStrs), 1))
                       .replace('%NESTED-INTERFACE-DEFS%', util.indent(''.join(innerIntfDefs), 1)))

def getClassDef(schemaName, enumDef, structDef, arrElemTypes, genIntf, fldComments):
    enumDefStrList = []
    if genIntf:
        optPublic = ''
        intfType = misc.getIntfName(schemaName)
        optImplements = ' implements ' + intfType + ', ConfigAccess'
    else:
        optPublic = 'public '
        intfType = None
        optImplements = ' implements ConfigAccess'
        enumDefStrList = _getEnumDefStrList(enumDef, False)

    clasType = misc.getClasName(schemaName)
    structDesc = structDef[schemaName]

    # field related code: decl/accessor/set
    (fldDecls, fldAccessors, parseFields) = _getFieldRelatedCode(structDesc, enumDef, structDef, genIntf, True)
    # pprint method
    pprintMethod = _getPPrintMethodDef(structDesc, enumDef, structDef, (fldComments != None), True)
    # set method
    setMethodDef = _getSetMethodDef(schemaName, structDesc, enumDef, structDef, True)

    nvdkDefaultDef = '    private static final String NVDK_DEFAULT = "' + schemaParser.NVDK_DEFAULT + '";\n'
    innerClasses = _getInnerClassDefs(schemaName, enumDef, structDef, intfType, genIntf)
    arrayMethods = _getArrayMethodDefs(arrElemTypes, enumDef, structDef)

    # optForOutermost
    schema = dict()
    schema['%struct-def'] = structDef
    schemaJsonStr = json.dumps(schema, separators=(',', ':'))
    schemaJsonStr = schemaJsonStr.replace(r'\"', r'\\"').replace('"', r'\"')
    optForOutermost = _tmplOptForOutermost.replace('%SCHEMA-JSON-STR%', schemaJsonStr)

    # optPrivForOutermost
    if fldComments == None:
        optPrivForOutermost = _tmplOptPrivForOutermost.replace('%OPT-CONF-FLD-COMMENTS%', '')
    else:
        fldCommentsStr = json.dumps(fldComments, separators=(',', ':'))
        fldCommentsStr = fldCommentsStr.replace(r'\"', r'\\"').replace('"', r'\"').replace(r'\n', r'\\n')
        fldComments = _tmplFldComments.replace('%CONF-FLD-COMMENTS-STR%', fldCommentsStr)
        fldComments = util.indent(fldComments , 1);
        optPrivForOutermost = _tmplOptPrivForOutermost.replace('%OPT-CONF-FLD-COMMENTS%', fldComments)

    return (_tmplTopClassDef
                .replace('%OPT-FOR-OUTERMOST%', optForOutermost)
                .replace('%OPT-PUBLIC%', optPublic)
                .replace('%CLASS-TYPE%', clasType)
                .replace('%OPT-IMPLEMENTS%', optImplements)
                .replace('%FIELD-ACCESSORS%', util.indent('\n'.join(fldAccessors), 1))
                .replace('%FIELD-DECLS%', util.indent('\n'.join(fldDecls), 1))
                .replace('%ARRAY-METHODS%', arrayMethods)
                .replace('%STRUCT-NAME%', schemaName)
                .replace('%PARSE-FIELDS%', util.indent('\n'.join(parseFields), 2))
                .replace('%NESTED-CLASSES%', innerClasses)
                .replace('%ENUM-DEFS%', ''.join(enumDefStrList) if len(enumDefStrList) > 0 else '')
                .replace('%NVDK-DEFAULT-DEF%', nvdkDefaultDef)
                .replace('%OPT-PRIV-FOR-OUTERMOST%', optPrivForOutermost)
                .replace('%PPRINT-METHOD%', util.indent(pprintMethod, 1))
                .replace('%SET-METHOD%', util.indent(setMethodDef, 1))
            )

