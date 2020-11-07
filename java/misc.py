from common import util

def createJavaFile(clsName, package, targetDir, imports):
    f = util.createFile(targetDir + '/' + clsName + '.java')
    util.writeln(f, 'package ' + package + ';')
    util.writeln(f, '')
    for i in imports:
        util.writeln(f, 'import ' + i + ';')
    return f

def getTypeName(name):
    return name.capitalize()

def getIntfName(name):
    return getTypeName(name)

def getClasName(name):
    return getIntfName(name) + 'Base'
