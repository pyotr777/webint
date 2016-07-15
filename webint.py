#!/usr/bin/env python
#
# Web interface for executing shell commands
# 2016 (C) Bryzgalov Peter @ CIT Stair Lab

ver = "0.2-13"

import bottle
import subprocess
import re
import urllib
import os
import sys
import json
from lxml import etree
import StringIO
from gevent import monkey; monkey.patch_all()

import gevent
from bottle.ext.websocket import GeventWebSocketServer
from bottle.ext.websocket import websocket

webint = bottle.Bottle()

# Base folder
try:
    base_folder = os.environ["WEBINT_BASE"]
except:
    web_folder = os.getcwd()+"/webfiles"
# Template file names
html_base = "index.html"
static_folder = web_folder+"/static"
default_block = web_folder+"/default.html"
block_counter = 1

print "Webint v" + str(ver)
print "Base folder  : " + web_folder
print "Base page    : " + web_folder + "/" + html_base
print "Static folder: " + static_folder
print "Default block: " + default_block


# Permitted hosts
accessList = ["localhost","127.0.0.1"]
# Allowed commands
allowed_commands = []
allowed_commands.append("git\s([a-zA-Z0-9\.])*")
allowed_commands.append("ls\s([a-zA-Z0-9\.\-])*")
allowed_commands.append("echo\s([a-zA-Z0-9\.\-\s])*")
allowed_commands.append("find\s([a-zA-Z0-9\.])*")
allowed_commands.append("pwd")
allowed_commands.append("whoami")
allowed_commands.append("./test.sh")

# Commands patterns have been compiled flag
compiled = False
compiled_dic = {}


# Check access origin
def allowAccess():
    remoteaddr = bottle.request.environ.get('REMOTE_ADDR')
    forwarded = bottle.request.environ.get('HTTP_X_FORWARDED_FOR')

    if (remoteaddr in accessList) or (forwarded in accessList):
        return True
    else:
        return False

def allowCommand(test_command):
    global compiled
    global compiled_dic
    if not test_command:
        return False
    print "Checking command "+ test_command
    if not compiled:
        print "Compiling command patterns"
        for command in allowed_commands:
            # print command.pattern_str
            compiled_dic[command] = re.compile(command)
        compiled = True
    for pattern_str in compiled_dic:
        pattern = compiled_dic[pattern_str]
        # print "Checking pattern " + pattern_str
        # print test_command
        if pattern.match(test_command) is not None:
            # print "Command "+test_command+" matched pattern " + pattern_str
            return True
    print "No patterns matched. Command "+test_command+" not allowed."
    return False

# Execute command in shell
# and return its stdout and stderr streams.
def Execute(command) :
    #output = subprocess.check_output(command.split(),stderr=subprocess.STDOUT)
    print "Executing " + command
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True,  bufsize=1)
    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            yield line,
    proc.wait()


# Now only returns output.
# In the future - analyse output.
def displayOutput(command, output):
    global block_counter
    block_counter += 1
    print "Displaying output in " + default_block
    # Default DIV block transformations
    div_transform_id = "someid"    
    div_block_file = open(default_block)
    outfilename = static_folder + "/block" + str(block_counter) + ".html"
    print "Write to " + outfilename
    out_block_file = open(outfilename, 'w')
    div = div_block_file.read()
    # Replace default IDs with block unique IDs
    div = re.sub(r'NNN',str(block_counter),div)
    # Insert output
    div = re.sub(r'OUTPUT',output,div)
    # And command
    div = re.sub(r'COMMAND',command,div)
    # Replace block number variable i in javascript
    div = re.sub(r'var\s*i\s*=\s*1[;]*',r'var i = '+str(block_counter), div)

    out_block_file.write(div)
    out_block_file.write("\n")
    out_block_file.close()
    div_block_file.close()
    return div


# Workflow Start
#Display emtpy HTML template with command field.
@webint.route('/')
def show_template():
    if allowAccess():
        pass
    else:
        return "Access denied."
    print "Reading base page "+ html_base
    return bottle.static_file(html_base, root=web_folder)


@webint.route('/<filename>')
def show_html(filename):
    if allowAccess():
        pass
    else:
        return "Access denied."
    print "Read page "+ filename
    return bottle.static_file(filename, root=web_folder)

@webint.route('/static/<filepath:path>')
def serv_static(filepath):
    print "Serve file " + filepath + " from " +static_folder
    return bottle.static_file(filepath, root=static_folder)


@webint.route('/exec/<esc_command:path>')
def exec_command(esc_command='pwd'):
    print "Exec_command " + esc_command
    command = urllib.unquote_plus(esc_command)
    print "Executing " + command
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=1)
    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            print "* "+ line,
            yield line
    proc.wait()


# Add / replace parts of XML file
@webint.post('/xml/edit/<filepath:path>')
def edit_xml(filepath):
    #path = bottle.request.forms.get('filepath')
    out = StringIO.StringIO()
    err = StringIO.StringIO()
    out.write('')
    print >> out, "Received XML request for file " + filepath 
    # Open file
    try:
        f = etree.parse("webfiles/" +filepath)
    except IOError as ex:
        print  >> err, "Error reading file " + "webfiles/" + filepath
        stdout = out.getvalue()
        stderr = err.getvalue()
        out.close()
        err.close()
        return json.dumps({'stdout':stdout, 'stderr':stderr})
    #print  >> out, etree.tostring(f)
    
    keys = bottle.request.forms.keys()
    for key in keys:
        val = bottle.request.forms.get(key)
        print  >> out, "key="+key+" val="+val 
        try:
            node = f.xpath(key)
            node[0].text = val
        except etree.XPathEvalError:
            print >> err, "Wrong path syntax: " + key 
            stdout = out.getvalue()
            stderr = err.getvalue()
            out.close()
            err.close()
            return json.dumps({'stdout':stdout, 'stderr':stderr})

        except:
            print >> err, sys.exc_info()
            print >> err, "Not found: " + key
            stdout = out.getvalue()
            stderr = err.getvalue()
            out.close()
            err.close()
            return json.dumps({'stdout':stdout, 'stderr':stderr})
   
    print  >> out, etree.tostring(f) 
    print etree.tostring(f) 
    # Return stdout and stderr
    stdout = out.getvalue()
    stderr = err.getvalue()
    out.close()
    err.close()
    return json.dumps({'stdout':stdout, 'stderr':stderr})

@webint.route('/stream')
def stream():
    yield 'START<br>'
    gevent.sleep(2)
    yield 'MIDDLE<br>'
    gevent.sleep(2)
    yield 'END'

@webint.get('/websocket', apply=[websocket])
def echo(ws):
    while True:
        msg = ws.receive()
        print "Rec: " + msg

        if allowAccess():
            pass
        else:
            ws.send("Access denied.")
            break
 
        command = urllib.unquote_plus(msg)
        print "Have command " + command + "."
        if allowCommand(command):
            pass
        else:
            return displayOutput(command, "Command not allowed.")

        proc = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=1)
        with proc.stdout:
            for line in iter(proc.stdout.readline, b''):
                print line,            
                ws.send(line)
        proc.wait()
        print "finish"
        break




        msg = "Server " + msg
        if msg is not None:
            print "Snd: " + msg
            ws.send(msg)
        else: break

@webint.route('/exe', apply=[websocket])
def exe(ws):
    proc = subprocess.Popen("./test.sh", stdout=subprocess.PIPE, bufsize=1)
    i = 0;
    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            print "* "+ line,            
            ws.send("<p style=\"background-color:rgb(100,100,"+str(i*25)+")\">"+line+"</p>")
            i += 1
    proc.wait()
    print "finish"
    return


bottle.run(webint,host='localhost', port=8080, debug=True, server=GeventWebSocketServer)


