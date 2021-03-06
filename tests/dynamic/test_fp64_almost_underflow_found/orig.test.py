#!/usr/bin/env python

import subprocess

# returns: tuple (type, error, op, file, line)
#
#+-------------------------- FPChecker Warning Report --------------------------+
# Error         : Underflow                                                      
# Operation     : ADD                                                            
# File          : dot_product.cu                                                 
# Line          : 9                                                              
#+------------------------------------------------------------------------------+
#
def getFPCReport(lines):
    ret = ("", "", "", "", "")
    for i in range(len(lines)):
        l = lines[i]
        if "FPChecker" in l and "Report" in l and "+" in l:
            typ = l.split()[2]
            err = lines[i+1].split()[2]
            op = lines[i+2].split()[2]
            f = lines[i+3].split()[2]
            line = lines[i+4].split()[2]
            ret = (typ, err, op, f, line)
            break

    return ret

def main():
    # --- compile code ---
    cmd = ["make -f Makefile.1"]
    try:
        cmdOutput_1 = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
	exit()

    # --- run code ---
    cmd = ["./main"]
    try:
        cmdOutput_1 = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
        exit()


    # --- compile code ---
    cmd = ["make -f Makefile.2"]
    try:
        cmdOutput_2 = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
        exit()

    # --- run code ---
    cmd = ["./main"]
    try:
        cmdOutput_2 = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        print e.output
        exit()


    rep1 = getFPCReport(cmdOutput_1.split("\n"))
    rep2 = getFPCReport(cmdOutput_2.split("\n"))

    if rep1[0] == 'Warning' and rep1[1] == 'Underflow' and rep1[4] == '8' and rep2[0] == "":
        print "PASSED"
    else:
        print "failed"

main()

