#!/usr/bin/env python

import subprocess
import os

def setup_module(module):
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    os.chdir(THIS_DIR)

def teardown_module(module):
    cmd = ["make -f Makefile.1 clean"]
    cmdOutput = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)


# returns: tuple (error, op, file, line)
#
#+-------------------------- FPChecker Warning Report --------------------------+
# Error         : Underflow                                                      
# Operation     : ADD                                                            
# File          : dot_product.cu                                                 
# Line          : 9                                                              
#+------------------------------------------------------------------------------+
#
def getFPCReport(lines):
    ret = ("", "", "", "")
    for i in range(len(lines)):
        l = lines[i]
        if "FPChecker" in l and "Report" in l and "+" in l:
            err = lines[i+1].split()[2]
            op = lines[i+2].split()[2]
            f = lines[i+3].split()[2]
            line = lines[i+4].split()[2]
            ret = (err, op, f, line)
            break

    return ret

def test_1():
    # --- compile code ---
    cmd = ["make -f Makefile.1"]
    try:
        cmdOutput = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
	exit()

    # --- run code ---
    cmd = ["./main"]
    try:
        cmdOutput = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
        exit()

    rep1 = getFPCReport(cmdOutput.split("\n"))

    # --- compile code ---
    cmd = ["make -f Makefile.2"]
    try:
        cmdOutput = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
        exit()

    # --- run code ---
    cmd = ["./main"]
    try:
        cmdOutput = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
        exit()

    rep2 = getFPCReport(cmdOutput.split("\n"))

    assert rep1[0] == 'INF' and rep1[3] == '10' and rep2[0] == 'INF' and rep2[3] == '12'

