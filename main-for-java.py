import getopt, sys, os

from common import schemaParser, sampleGenerator
from java import misc, loaderGenerator

def _printUsage():
    print('usage:')
    print('python3 -m json-schema/java <schema name> <sample directory> <package root directory> ' +
          '<class package> [ -i|--interface-package <interface package> ] <schema file> ...')

def _checkArgs(schemaName, sampleDir, pkgRootDir, clasPkg, intfPkg, schemaFiles):
    print('')
    print('  schema name: ' + schemaName)
    print('   sample dir: ' + sampleDir)
    print(' pkg root dir: ' + pkgRootDir)
    print('    class pkg: ' + clasPkg)
    print('interface pkg: ' + intfPkg)
    print(' schema files: ' + str(schemaFiles))
    print('')

    # sample dir must exist
    if not os.path.isdir(sampleDir):
        print('error: ' + sampleDir + ' is not an existing directory');
        sys.exit(1)

    # package root dir must exist
    if not os.path.isdir(pkgRootDir):
        print('error: ' + pkgRootDir + ' is not an existing directory');
        sys.exit(1)

    # class dir must exist
    clasDir = pkgRootDir + '/' + clasPkg.replace('.', '/')
    if not os.path.isdir(clasDir):
        print('creating a directory ' + clasDir + ' to put the generated implementation class file in');
        os.makedirs(clasDir)

    # interface dir must exist
    if intfPkg:
        intfDir = pkgRootDir + '/' + intfPkg.replace('.', '/')
        if not os.path.isdir(intfDir):
            print('creating a directory ' + intfDir + ' to put the generated interface file in');
            os.makedirs(intfDir)
    else:
        intfDir = None

    return (clasDir, intfDir)

def main():
    if len(sys.argv) < 6:
        _printUsage()
        sys.exit(1)

    schemaName = sys.argv[1]
    sampleDir = sys.argv[2]
    pkgRootDir = sys.argv[3]
    clasPkg = sys.argv[4]

    try:
        opts, schemaFiles = getopt.getopt(sys.argv[5:], "i:", ['interface-package='])
    except getopt.GetoptError as err:
        print(err)
        _printUsage()
        sys.exit(1)

    intfPkg = None  # default is not to generate an interface

    for o, a in opts:
        if o == '-i' or o == '--interface-package':
            intfPkg = a
        else:
            assert False, ('illegal option ' + o)

    (clasDir, intfDir) = _checkArgs(schemaName, sampleDir, pkgRootDir, clasPkg, intfPkg, schemaFiles)

    (enumDef, structDef, arrElemTypes) = schemaParser.parse(schemaName, schemaFiles)

    samplePath = sampleDir + '/' + schemaName + '.sample.json'
    fldComments = sampleGenerator.generate(samplePath, enumDef, structDef, schemaName)
    assert fldComments != None

    genIntf = (intfPkg != None)

    if genIntf:
        # create a java file defining the interface
        intfName = misc.getIntfName(schemaName)
        print("creating the interface file " + intfDir + '/' + intfName + '.java')
        intfFile = misc.createJavaFile(intfName, intfPkg, intfDir, [
                "io.github.hyunikn.jsonschema.UINT64"
        ])
        try:
            loaderGenerator.writeIntf(intfFile, enumDef, structDef, schemaName)
        except:
            intfFile.close()
            os.remove(intfFile.name)
            raise

        intfFile.close()

    # create a java file defining the implementation class
    imports = [
        "io.github.hyunikn.jsonschema.JsonSchema",
        "io.github.hyunikn.jsonschema.ConfigAccess",
        "io.github.hyunikn.jsonschema.UINT64",
        "com.github.hyunikn.jsonden.*",
        'io.github.getify.minify.Minify',
        'java.io.File',
        'java.io.FileOutputStream',
        'java.util.TreeSet',
        'java.util.Set',
    ]
    if genIntf:
        imports.append(intfPkg + '.' + intfName)

    clasName = misc.getClasName(schemaName)
    print("creating the implementation class file " + clasDir + '/' + clasName + '.java')
    clasFile = misc.createJavaFile(clasName, clasPkg, clasDir, imports)
    try:
        clasDef = loaderGenerator.getClassDef(schemaName, enumDef, structDef, arrElemTypes, genIntf, fldComments)
        clasFile.write(clasDef)
    except:
        clasFile.close()
        os.remove(clasFile.name)
        raise

    clasFile.close()

if __name__ == '__main__':
    main()
else:
    raise Exception('can only be run')
