numCounts="ACQ:AVA?"
numCountsKey=":ACQuire:SEGMented:COUNT?"  #NC:4 (NC=1,2,3,4,5)
headerOff=":SYSTem:HEADer OFF"
currmeasKey=":MEASure:STATistics CURRENT"
resultKey=":MEASure1:RESults?"
modeSegment=" :WAVeform:SEGMented:ALL OFF"
waveformkey=":WAVeform:DATA?"
ascii="FORM ASCii"
asciiKey=":WAVeform:FORMat ASCii"
lsbf="FORM:BORD LSBF"
lsbfKey=":WAVeform:BYTEorder LSBFirst"
#waveform="CHAN:DATA?"
rdy="*OPC?"
idn="*IDN?"
tsr="CHAN:HIST:TSR?"
tsrKey=":TRIGger:DELay:TDELay:TIME?"
lvlTrigger="TRIGger:A:LEVel1?"      
lvlTriggerKey=":TRIGger:LEVel? CHANnel1" #NC=5
arate="ACQuire:POINts:ARATe?"  #puede que sea el :ACQuire:SRATe:ANALog? para arate y el 
arateKey=":MEASure:DATarate?"
segmentPKey=":WAVeform:SEGMented:POINts?"
srate="ACQuire:SRATe?"
srateKey=":ACQuire:SRATe:ANALog?"   #creo
timeBase="TIMebase:SCALe?"  #NC=5
timeBaseKey=":TIMebase:SCALe?"
saveTS="EXPort:ATABle:SAVE"
pulse="C1:BSWV WVTP,PULSE"
Bin="FORM BIN"
posC1="CURSor1:Y1Position?"
posC2="CURSor1:Y2Position?"
rst="*RST"  
voltMode=":SOUR:VOLT:MODE VOLT" 
sweepMode=":SOUR:VOLT:MODE SWE"  
sweepSing=":SOUR:SWE:STA SING"  
sweepLin=":SOUR:SWE:SPAC LIN"   
smuAuto1=":sens:func ""curr"""  
smuAuto2=":sens:curr:nplc 0.1"  
smuAuto3=":sens:curr:prot 0.01" 
smuTrig=":trig:sour aint"
smuOn=":outp on"
smuInit=":init (@1)"
queryCurr=":fetc:arr:curr? (@1)"
queryVolt=":fetc:arr:volt? (@1)"
smuOff=":outp off"
test=":MEASure:DATarate? CHANnel2"
test="*IDN?"

#def levelTriggerKey(channel):
#    return ":TRIGger:LEVel? CHAN"+str(channel)

def openHist(channel):
    return "CHAN"+channel+":HIST:STAT ON"

def selectCurr(trigg, i):
    return "CHAN:HIST:CURR " + str(-int(trigg)+(i+1))

def selectCurrKey(trigg, i):
    return " :ACQuire:SEGMented:INDex " + str(i)

def selectCurrMath(trigg, i):
    return "CALC:MATH1:HIST:CURR " + str(-int(trigg)+(i+1))

def waveform(channel):
    return "CHAN"+channel+":DATA?"

def waveformMath(channel):
    return "CALC:MATH"+channel+":DATA?"

def selectChanCur(channel):
    return "CURSor1:SOURce " + str(channel)

def  channelKey(channel):
    return ":WAV:SOURCE CHAN"+str(channel)

