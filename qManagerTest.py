#! python3

import socket
import json
from tkinter.filedialog import askopenfilename as AOFN
import tkinter
from pprint import pprint
import time

Queue=[]
Script=[]
dict= "The following are accepted commands: help, Read Script, Exit, TEST, QUIT,... tbc"

def main(s,Queue,Script):
	Element=None
	while(Element!="Exit"):
		Element, Queue = dequeueElement(Queue)
		if(Element==None):
			command=Poll()
			Queue=enqueueElement(Queue,command)
			
		elif(Element=="help"):
			print(dict)
	
		elif(Element=="Read Script"):
			Script= readScript()
			
		elif(Element=="Run Script"):
			runScript(s, Script)
			
		elif(Element!="Exit"):
			Parameter = input('If command chosen has a parameter, please enter that now:')
			sendCMDandRecvAck(s,Element,[Parameter])
			
		elif(Element=="Exit"):
			sendCMDandRecvAck(s,Element,'')
			
		else:
			return None
	return None		
def Poll():
	command = input('Enter desired command:')
	return command
def enqueueElement(Queue,Element):
	Queue.append(Element)
	return Queue	
def dequeueElement(Queue):
	try:
		Element= Queue[0]
		Queue=Queue[1:]
	except IndexError:
		Element=None
		Queue=[]
	return Element, Queue	
def sendWithSize(s,cmd):
	size= len(cmd)
	size= [0,0,0,size]
	size=bytes(size)
	cmd=bytes(cmd,'ascii')
	cmd=size+cmd
	s.send(cmd)	
def commandWithParameter(commArray):
	commandString=''
	for i in commArray:
		commandString+= i + '	'
	return commandString	
def readWithSize(s):
	size= s.recv(4)
	size=size[3]
	data = s.recv(size)
	data = bytes.decode(data)
	data= data.split()
	return data	
def sendCMDandRecvAck(s,element,parameter): #parameter must be a list []
	command= [element]+parameter
	CommandPackage=commandWithParameter(command)
	sendWithSize(s,CommandPackage)
	data = readWithSize(s)
	print("received data:", data) #get ok
	data = readWithSize(s)
	print("received data:", data) #wait for done	
def initTCP():
	#host = socket.gethostname() #for local connection
	host = '139.229.15.132'
	port = 6009
	s = socket.socket()
	s.connect((host,port))
	return s	
def readScript():
	root= tkinter.Tk()
	filename = AOFN(filetypes= (("Text Files",".txt"),("All files", "*.*") ))
	root.destroy()
	fp=open(filename)
	Script= json.load(fp)
	pprint(Script)
	return Script
def runScript(s,Script):
	currentTarget=["00:00:00.00","00:00:00.00"] #RA, DEC
	compMirrorStatus=False #true for in, false for out
	currentLampPercents=[]
	for i in range(len(Script)):
		i=i+1
		line=Script[str(i)]
		targetPause, usingLamps, compMirrorPause, usingSlit=precheck(line,currentTarget)
		#Move Telescope
		if(targetPause):
			moveToTarget(s,line) #shouldnt progress until done is recv
	
		#Move to setup
		moveToSetup(s,line)
		setupDone,camsetDone=False,False
		while(setupDone!=True or camsetDone!=True):
			#set a timeout
			response=readWithSize(s)
			if(response=="DONE CAMSET"):
				camsetDone=True
				print("Camera Setup Done")
			elif(response=="DONE SETUP" or response=="DONE SETUPNOCHANGE"):
				setupDone=True
				print("Instument Setup Done")
			else:
				print(response)
		# Comp Mirror
		if(compMirrorPause):
			if(usingLamps):
				toggleCompMirror(s,"IN") # if im using lamps and have the comp pause, put in mirror first
				compMirrorStatus=True # once pause is used up clear it
			else:
				toggleCompMirror(s,"OUT") # if not using lamps and have comp pause, need to remove mirror
				compMirrorStatus=False
		#Lamps		
		sendLamps(s,line) 
		#Slit pause
		input('Press Enter when Slit is aligned and target acquired')
		#Send Start command	
		acquire(s)
		# line done
		print("line " +str(i)+" of " +str(len(Script))+ " complete!")
		
	print("Script Complete")	
def precheck(line, currentTarget):
	lampStatus=[]
	targetPause=(currentTarget==[line["RA (HH:MM:SS.SS"] , line["DEC (HH:MM:SS.SS)"]])
	for lamp in ["Ar","Bulb","Cu","Dome","Fe","Hg(Ar)","Ne","Quartz"]:
		lampStatus.append(line["SI camera info"][lamp])
	usingLamps=any(lampStatus)
	compMirrorPause=(compMirrorStatus!=usingLamps)
	usingSlit=(line["Configuration"]["Slit Mask"] !='<No Mask>')
	return targetPause, usingLamps, compMirrorPause, usingSlit
def moveToTarget(s, line):
	RA = line["RA (HH:MM:SS.SS)"]
	DEC= line["Dec (HH:MM:SS.SS)"]
	sendCMDandRecvAck(s,"TARGET", [RA, DEC])
def moveToSetup(s,line):
	configuration= line["Configuration"]
	camInfo=line["SI camera info"]
	camParams = [str(camInfo["Observer Name"]),str(camInfo["object name"]),str(camInfo["File name Base"]),
				str(camInfo["Notes"]),str(camInfo["Exp type tab"]),str(camInfo["Number of Exp"]),
				str(camInfo["Exp time"]),str(camInfo["CCD Readout Speed"]),str(camInfo["CCD ROI Mode"]),str(camInfo["Custom Roi"]['0']), 
				str(camInfo["Custom Roi"]['1']),str(camInfo["Custom Roi"]['2']),str(camInfo["Custom Roi"]['3']),str(camInfo["Custom Roi"]['4']),
				str(camInfo["Custom Roi"]['5'])]
	configParams= [ str(configuration["Primary Filter"]),str(configuration["Secondary Filter"]),str(configuration["Slit Mask"]),
					str(configuration["Grating"]),str(configuration["CS Target"]),str(configuration["GS Target"]),str(configuration["Coll Focus"]),
					str(configuration["Camera Focus"]), str(configuration["use Flexure Comp?"]),str(configuration["Select Mode:"]) ]
	camCMD = commandWithParameter(["CAMSET"]+camParams)
	configCMD= commandWithParameter(["SETUP"]+configParams)
	sendWithSize(s,camCMD)
	response=readWithSize(s)
	print(response)
	sendWithSize(s,configCMD)
	response=readWithSize(s)
	print(response)
	if("Focus"==str(camInfo["Exp type tab"])):
		focusCMD=commandWithParameter(["FOCUS"]+[str(camInfo["Start"])]+[str(camInfo["Delta"])]+[str(camInfo["Stop"])])
		sendWithSize(s,focusCMD)
		response=readWithSize(s)
		print(response)
def sendLamps(s,line): #currently sleeps for 15 seconds after getting okay
	lampStatus=[]
	for lamp in ["Hg(Ar)","Cu","Ne","Bulb","Ar","Fe","Quartz","Dome"]:
		lampStatus.append(str(line["SI camera info"][lamp]))
	lampStatus.append(str(line["SI camera info"]["Quartz Percent"]))
	lampStatus.append(str(line["SI camera info"]["Dome Percent"]))
	for i in lampStatus:
		if(i=="True"):
			i="ON"
		elif(i=="False"):
			i="OFF"
	lampCMD= commandWithParameter(["LAMPS"] + lampStatus )
	sendWithSize(s,lampCMD)
	response=readWithSize(s)
	print(response)
	time.sleep(15)
def toggleCompMirror(s, status):
	sendCMDandRecvAck(s,"MIRROR",[status])
def acquire(s):
	sendWithSize(s,"START")
	response=readWithSize(s)
	print(response)
	print("Exposure Active")
	while(imageDone!=True):
		#timeout condition
		response=readWithSize(s)
		if(response=="DONE Acquisition Done"):
			imageDone=True
	print("Acquisition Done")
	
	
s= initTCP()
main(s,Queue,Script)
s.close()




