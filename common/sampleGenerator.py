import json
import os
import sys
import codecs

from . import util, schemaParser, builtInTypes

_MAX_DESC_WIDTH = 80    # TODO: parameterize this

def _getTypeText(schemaName, enumDefs, structDefs, ty, level, structNameStack):
    if isinstance(ty, list):
        return 'array of ' + _getTypeText(schemaName, enumDefs, structDefs, ty[0], level, structNameStack)
    else:
        assert util.isString(ty)
        if ty in builtInTypes.types:
            return ty
        elif ty in enumDefs:
            enumLines = []
            enumLines.append('enum [')
            for i in enumDefs[ty]:
                enumLines.append('  "' + i + '"')   # indent of size 2
            enumLines.append(']')
            return '\n'.join(enumLines)
        elif ty in structDefs:
            visited = False
            for s in structNameStack:
                if s == ty:
                    visited = True
                    break
            if visited:
                assert not ty.startswith(schemaName + '__')
                return 'struct ' + ty
            else:
                return ('struct ' + ('' if ty.startswith(schemaName + '__') else (ty + ' ')) +
                        _getStructText(None, schemaName, enumDefs, structDefs, ty, level + 1, structNameStack))
        else:
            assert False


def _getValueText(val):
    return json.dumps(val, sort_keys=False, indent=2, separators=(',', ': '))

def _appendCommentToFirstLine(text, comment):
    if comment:
        lines = text.splitlines()
        lines[0] = lines[0] + ' /* ' + comment + ' */'
        return '\n'.join(lines)
    else:
        return text

def _getStructText(confFldComments, schemaName, enumDefs, structDefs, structName, level, structNameStack):
    structDesc = structDefs[structName]
    assert structDesc != None

    structNameStack.append(structName)

    fldLines = []
    fldNames = list(structDesc.keys())
    fldNames.sort()
    for fldName in fldNames:
        fldDesc = structDesc[fldName]
        fldType = fldDesc[schemaParser.NVDK_TYPE]
        hasFldDefault = (schemaParser.NVDK_DEFAULT in fldDesc)
        fldDefault = fldDesc[schemaParser.NVDK_DEFAULT] if hasFldDefault else None

        ## comment
        ##
        commentLines = []
        commentLines.append('field: ' + fldName)
        descWidth = _MAX_DESC_WIDTH - 4 - 3 * (level + 1)
        commentLines.append(util.indent(util.lineBreak(fldDesc[schemaParser.NVDK_DESC], descWidth), 1, 2))
        commentLines.append('type: ' + _getTypeText(schemaName, enumDefs, structDefs, fldType, level, structNameStack))
        commentLines.append('settable: ' + ('yes' if fldDesc[schemaParser.NVDK_SETTABLE] else 'no'))
        commentLines.append('default: ' + (_getValueText(fldDefault) if hasFldDefault else '<none>'))
        if level == 0:
            commentLines = util.lineComment('\n'.join(commentLines))
        else:
            commentLines = util.prefixLines('\n'.join(commentLines), '. ')

        valueLines = ''
        if level == 0:
            ## value
            ##
            assert confFldComments != None
            confFldComments[fldName] = util.indent(commentLines, 1, 2)

            marker = ''
            if schemaParser.NVDK_SAMPLE in fldDesc:
                fldSample = fldDesc[schemaParser.NVDK_SAMPLE]
                valueLines = '"' + fldName + '": ' + _getValueText(fldSample) + ','
                marker = '%sample'
            else:
                if hasFldDefault:
                    valueLines = '"' + fldName + '": %default,'
                    valueLines = util.lineComment(valueLines)
                    marker = None
                else:
                    valueLines = util.lineComment('"' + fldName + '": <undefined>,')
                    marker = '%sample'
            valueLines = _appendCommentToFirstLine(valueLines, marker)
        else:
            ## field name in the struct type
            ##
            assert confFldComments == None
            valueLines = '"' + fldName + '"'

        fldLines.append('\n' + util.indent(commentLines + '\n' + valueLines, 1, 2 if level == 0 else 1))

    if (len(fldNames) > 0) and (level == 0):
        fldLines.append('\n\n  "%end%": null')

    structNameStack.pop()

    return '{' + '\n'.join(fldLines) + '\n}'

def generate(path, enumDefs, structDefs, schemaName):
    assert path != '%NONE%'

    print('creating a sample file ' + path)

    structNameStack = []    # without this, _getStructText can fall into an infinite loop for
                            # mutually recursive struct definitions
    confFldComments = {}
    with codecs.open(path, 'w', encoding='utf-8') as f:
        try:
            text = _getStructText(confFldComments, schemaName, enumDefs, structDefs, schemaName, 0, structNameStack)
        except:
            f.close()
            os.remove(path)
            raise

        f.write(text)
        f.close()

    return confFldComments
