#!/usr/bin/env python3

import json
import pathlib
import argparse
import subprocess
import sys
import os
from nvcc_parser import ClangCommand
from colors import prGreen,prCyan,prRed
import strace_module

FPCHECKER_PATH      ='/usr/global/tools/fpchecker/blueos_3_ppc64le_ib_p9/fpchecker-0.1.2-clang-9.0.0'

# -------- LLVM version -------------
#LLVM_PASS_LLVM = '-Xclang -load -Xclang ' + FPCHECKER_PATH + '/lib64/libfpchecker.so -include Runtime.h ' + '-I' + FPCHECKER_PATH + '/src'
LLVM_PASS_LLVM = '-Xclang -load -Xclang ' + FPCHECKER_PATH + '/lib64/libfpchecker.so -include ./Runtime.h ' #+ '-I' + FPCHECKER_PATH + '/src'

# ------- Clang version ---------
#FPCHECKER_LIB       =FPCHECKER_PATH+'/lib64/libfpchecker_plugin.so'
#FPCHECKER_RUNTIME   =FPCHECKER_PATH+'/src/Runtime_plugin.h'
FPCHECKER_LIB       ='/usr/workspace/wsa/laguna/fpchecker/FPChecker/build/libfpchecker_plugin.so'
FPCHECKER_RUNTIME   ='/usr/workspace/wsa/laguna/fpchecker/FPChecker/src/Runtime_plugin.h'
CLANG_PLUGIN        ='-Xclang -load -Xclang '+FPCHECKER_LIB+' -Xclang -plugin -Xclang instrumentation_plugin'
LLVM_PASS_CLANG     =CLANG_PLUGIN+' -include '+FPCHECKER_RUNTIME+' -emit-llvm'

#REPLACE_SINGLE_OPTIONS = {'--device-c':'-fcuda-rdc', '-dc':'-fcuda-rdc', '-arch':'--cuda-gpu-arch', '--gpu-architecture':'--cuda-gpu-arch', '-G':' '}
#REPLACE_OPT_VALUES = {'-x':('cu', 'cuda')}
#REMOVE_OPTS_WITH_VALUES = ['--compiler-bindir', '-ccbin', '--ptxas-options', '-Xptxas']
ADD_OPTIONS = ['-Qunused-arguments', '-g']

CUDA_EXTENSION = ['.cu', '.cuda'] + ['.C', '.cc', '.cpp', '.CPP', '.c++', '.cp', '.cxx']

NVCC_ADDED_FLAGS = []

COMMANDS_DB = []

CLANG_VERSION = True 

#LINKER = None

#OMIT_SOURCE_FILES = ['POLYBENCH_GEMVER-Cuda_copy.cpp']
OMIT_SOURCE_FILES = []

RESTART_COMMAND = 1

# Defines a mapping of original names and new names for files
FILE_NAMES_MAP = {'file1': 'file1_copy'}

def modifyArchiveCommandIfNeeded(line):
  found = False
  tokens = line.split()
  ar_idx = None
  for t in tokens:
    if t == 'ar' or t.endswith('/ar'):
      ar_idx = tokens.index(t)
      break
  # We found the ar command
  library_idx = None
  if ar_idx != None:
    for t in tokens:
      if t.endswith('.a'):
        library_idx = tokens.index(t)
        break
  # We found the ar command and library:
  if ar_idx != None and library_idx != None:
    found = True
    for i in range(ar_idx+1, library_idx):
     tokens[i] = tokens[i].replace('q', 'r')
  line = ' '.join(tokens)
  return (found, line)

# Remove the object file option from the command line, i.e., -o file.o
def removeObjectFile(line, fileName):
  if '-o ' in line:
    tokens = line.split()
    idx = tokens.index('-o')
    objectName = tokens[idx+1]
    origName = os.path.splitext( os.path.split(objectName)[1] )[0]
    FILE_NAMES_MAP[origName] = origName
    del(tokens[idx])
    del(tokens[idx])
    line = ' '.join(tokens)
  else:
    name = os.path.splitext( os.path.split(fileName)[1] )[0]
    FILE_NAMES_MAP[name] = name+'_copy'

  return line

# Is it a link comand?
def isLinkCommand(line):
  if '-c ' not in line and '-o ' in line:
    return True
  return False 

# Is it the command that links the final program?
def isProgramLinkCommand(line):
  if '-c ' not in line and '-o ' in line:
    tokens = line.split()
    idx = tokens.index('-o')
    output = tokens[idx+1]
    if not output.endswith('.o'):
      return True
  return False 

def changeNameOfExecutable(line):
  tokens = line.split()
  idx = tokens.index('-o') + 1
  progName = tokens[idx]
  tokens[idx] = progName + '_fpc'
  line = ' '.join(tokens)
  return line

def changeNameOfObjectFiles(line):
  #print(FILE_NAMES_MAP)
  tokens = line.split()
  for i in range(len(tokens)):
    if tokens[i].endswith('.o'):
      name = os.path.splitext( os.path.split(tokens[i])[1] )[0]
      if name in FILE_NAMES_MAP:
        newObjectName = FILE_NAMES_MAP[name]
        newObjectName = os.path.join( os.path.split(tokens[i])[0], newObjectName+'.o')
        line = line.replace(tokens[i], newObjectName, 1)
  return line

def replaceFileName(line):
  fileName = getCodeFileName(line)
  newFileName = None
  if fileName != None:
    extension = fileName.split('.')[-1:][0]
    nameOnly = os.path.splitext(fileName)[0]
    newFileName = nameOnly+'_copy.'+extension
    line = line.replace(fileName, newFileName, 1)
  return (fileName, newFileName, line)

# Replace the original name of the source file
# Create a copy of the source file
def replaceFileNameAndCopy(line):
  (fileName, newFileName, line) = replaceFileName(line)
  if fileName != None:
    # Create a copy of the source file
    idx = line.index('clang++')
    copyCommand = '  cp -f ' + fileName + ' ' + newFileName + ' && '
    line = line[:idx] + copyCommand + line[idx:]
  return line, fileName

# Get the name of the file being compiled
def getCodeFileName(line):
  tokens = line.split()
  fileName = None
  for t in tokens:
    for ext in CUDA_EXTENSION:
      if t.endswith(ext):
        fileName = t
  return fileName

def isNVCC(line):
  return 'nvcc ' in line

def isClang(line):
  return 'clang++ ' in line

def convertCommand(line):
  if isProgramLinkCommand(line):
    line = changeNameOfExecutable(line)
    if CLANG_VERSION:
      line = changeNameOfObjectFiles(line)
    COMMANDS_DB.append([line, ''])
    return

  if isLinkCommand(line):
    COMMANDS_DB.append([line, ''])
    return

  # Check if it's archive command
  (found, line) = modifyArchiveCommandIfNeeded(line)
  if found:
    COMMANDS_DB.append([line, ''])
    return

  # Skip is not an nvcc compilation command
  if not isNVCC(line):
    COMMANDS_DB.append([line, ''])
    return

  newLine = ClangCommand(line).to_str()

  # Add options after clang command
  newLine = newLine.replace('clang++ ', 'clang++ '+' '.join(ADD_OPTIONS)+' ', 1)

  if CLANG_VERSION:
    newLine, origFileName = replaceFileNameAndCopy(newLine)
    newLine = removeObjectFile(newLine, origFileName)

  # Add original command
  origCommand = replaceFileName(line)[2]
  newNVCCCommand = 'nvcc -include ' + FPCHECKER_RUNTIME + ' '
  newNVCCCommand = newNVCCCommand + ' '.join(NVCC_ADDED_FLAGS) + ' '
  origCommand = origCommand.replace('nvcc ', newNVCCCommand)

  COMMANDS_DB.append([newLine, origCommand])

def replayCommands(fileName):
  global RESTART_COMMAND, OMIT_SOURCE_FILES

  with open(fileName) as fd:
    for line in fd:
      convertCommand(line)

  for i in range(len(COMMANDS_DB))[RESTART_COMMAND-1:]:
    cmd = COMMANDS_DB[i]

    # Omit some source files
    sourceFileName = getCodeFileName(cmd[0])
    if sourceFileName:
      for f in OMIT_SOURCE_FILES:
        if sourceFileName.endswith(f):
          cmd[0] = 'echo "Skipping: ' + f + '"'

    prCyan('Instrumenting ' + str(i+1) + '/' + str(len(COMMANDS_DB)))
    try:
      print(cmd[0])
      cmdOutput = subprocess.check_output(cmd[0], stderr=subprocess.STDOUT, shell=True)
      print(cmdOutput.decode('utf-8'))
    except subprocess.CalledProcessError as e:
      prRed('Error:')
      print(e.output.decode('utf-8'))
      exit(-1)

    if CLANG_VERSION:
      if cmd[1] != '':
        print(cmd[1])
        try:
          cmdOutput = subprocess.check_output(cmd[1], stderr=subprocess.STDOUT, shell=True)
          print(cmdOutput.decode('utf-8'))
        except subprocess.CalledProcessError as e:
          prRed('Error:')
          print(e.output.decode('utf-8'))
          exit(-1)

def execTraces(fileName):
  prGreen('Executing commands from ' + fileName)
  fd = open(fileName, 'r')
  i = 1
  total = len(fd)
  for cmd in fd:
    try:
      print(str(1) + '/' + total + ': ' + cmd[:-1])
      cmdOutput = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
      #print(cmdOutput.decode('utf-8'))
    except subprocess.CalledProcessError as e:
      prRed('Error:')
      print(e.output.decode('utf-8')) 
      exit(-1)
  fd.close()

def logConfigFile():
  global RESTART_COMMAND, OMIT_SOURCE_FILES
  confFile = './fpchecker_conf.json'
  if os.path.exists(confFile):
    print('Loading', confFile)
    data = None
    with open(confFile, 'r') as fd:
      data = json.load(fd)
    
    if data != None:
      for k in data.keys():
        if k == '--skip_files':
          OMIT_SOURCE_FILES = data[k]
        if k == '--restart_command':
          RESTART_COMMAND = data[k]

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='FPChecker tool')
  parser.add_argument('build_command',  help='Build command (e.g., make).', nargs=argparse.REMAINDER)
  parser.add_argument('--no-subnormal', action='store_true', help='Disable checking for subnormal numbers (underflows).')
  parser.add_argument('--no-warnings', action='store_true', help='Disable warnings of small or large numbers (overflows and underflows).')
  parser.add_argument('--no-abort', action='store_true', help='Print reports without aborting; allows to check for errors/warnings in the entire execution the program.')
  parser.add_argument('--no-checking', action='store_true', help='Do not perform any checking.')
  #parser.add_argument('--linker', help='Specify the linker.')
  parser.add_argument('--record', action='store_true', help='Record build traces only')
  parser.add_argument('--replay', action='store_true', help='Replay build traces (without instrumentation)')
  parser.add_argument('--inst-replay', action='store_true', help='Instrument and replay build traces')
  args = parser.parse_args()
  #print(args)
  #exit()

  prGreen('FPChecker')

  logConfigFile()

  if args.no_subnormal:
    NVCC_ADDED_FLAGS.append('-DFPC_DISABLE_SUBNORMAL')

  if args.no_warnings:
    NVCC_ADDED_FLAGS.append('-DFPC_DISABLE_WARNINGS')

  if args.no_abort:
    NVCC_ADDED_FLAGS.append('-DFPC_ERRORS_DONT_ABORT')

  if args.no_checking:
    NVCC_ADDED_FLAGS.append('-DFPC_DISABLE_CHECKING')

  if CLANG_VERSION:
    ADD_OPTIONS.append(LLVM_PASS_CLANG)
  else:
    ADD_OPTIONS.append(LLVM_PASS_LLVM)

  prog = args.build_command
  strace = strace_module.CommandsTracing(prog)


  if not args.record and not args.inst_replay:
    args.record = True
    args.inst_replay = True

  if args.record:
    prCyan('Tracing and saving compilation commands...')
    strace.startTracing()
    strace.analyzeTraces()
    strace.writeToFile()

  if args.replay:
    prCyan('Attempting to re-compile (without instrumentation)...')
    fileName = strace.getTracesDir() + '/executable_traces.txt'
    if os.path.exists(fileName):
      execTraces(fileName)
    else:
      prRed('Error no traces file found')
      exit(-1)

  if args.inst_replay:
    prCyan('Attempting to instrument and re-compile...')
    fileName = strace.getTracesDir() + '/executable_traces.txt'
    if os.path.exists(fileName):
      replayCommands(fileName)
    else:
      prRed('Error no traces file found')
      exit(-1)

