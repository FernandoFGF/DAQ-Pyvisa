import errno
import shutil
import os
from RsInstrument import * 
import zipfile
import winsound
from datetime import date
import time
import pyvisa
import dictionary_SCPI as ds
import numpy as np
import paramiko
from getpass import getpass; from getpass import getuser

#Func return de path output
def path(file):
    pathOUT='C:/Users/Ferna/Desktop/Laboratorio/Programacion-Automatizacion/Pyvisa/Output/'+ file + "/" + str(date.today())+"/"
    return pathOUT

#Func para la creacion de directorios
def create_dir(path):
    try:
        os.mkdir(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

import os

#Func para la creacion de directorios en el mismo sitio
def create_dir_in(nombre_carpeta):
    # Obtener la ruta del directorio de ejecución del script
    directorio_actual = os.getcwd()

    # Comprobar si la carpeta ya existe
    carpeta = os.path.join(directorio_actual, nombre_carpeta)
    if os.path.exists(carpeta):
        print(f"La carpeta '{nombre_carpeta}' ya existe en el directorio actual.")
    else:
        try:
            # Crear la carpeta
            os.mkdir(carpeta)
            print(f"Se ha creado la carpeta '{nombre_carpeta}' en el directorio actual.")
        except OSError:
            print(f"No se pudo crear la carpeta '{nombre_carpeta}'.")
    return carpeta


#Func para borrar directorio si existe
def delete_dir(filepath):
    if os.path.exists(filepath) and os.path.isdir(filepath):
        shutil.rmtree(filepath)  
    if os.path.exists(filepath) and os.path.isfile(filepath):
        os.remove(filepath) 

#Func para la creacion del ZIP
def create_zip(path, name):
    zip = zipfile.ZipFile(path +"/" + name +'.zip', 'w')
    for folder, subfolders, files in os.walk(path):
        for file in files:
            if file.endswith('.txt'):
                zip.write(os.path.join(folder, file), os.path.relpath(os.path.join(folder,file), path), compress_type = zipfile.ZIP_DEFLATED) 
    zip.close()

#Func alarma cuando acaba
def beep():
    for i in range(3):
        winsound.Beep(650-i*100, 500-i*50)

#Func contador en porcentaje
def counter_finish(i, finish):
    #if (round(i/int(finish)*100, 1)%5 == 0):
    print(str(round(i/int(finish)*100, 2))+" %")

#Func creacion fichero data (waveform)
def create_data(path, rta, startTime, len, scope):

    if(scope=='1'):

        trigger=float(rta.query(ds.lvlTrigger))
        aRate=float(rta.query(ds.arate))
        sRate=float(rta.query(ds.srate))
        timeB=float(rta.query(ds.timeBase))

        with open(path, 'w') as f:

            f.write('Resolucion(real): ' + str(sRate) + " ! "+ str(aRate) + ' Sa/s'+ '\n')
            f.write('Num de puntos(real): ' + str(len) + '\n')
            f.write('Time base scale: ' + str(timeB) + ' s'+ '\n')  
            f.write('Trigger (0.5PE): ' +str(trigger)+ ' v' +'\n')
            f.write('Tiempo de ejecucion: ' +str(round(((currentTime() - startTime)/60),2))+ ' min' +'\n')
        
        result=[timeB, str(len)]
    if(scope=='2'):

        trigger=float(rta.query('TRIG:LEVel1?'))
        aRate=float(rta.query(ds.arate))
        sRate=float(rta.query(ds.srate))
        timeB=float(rta.query(ds.timeBase))

        with open(path, 'w') as f:

            f.write('Resolucion(real): ' + str(sRate) + " ! "+ str(aRate) + ' Sa/s'+ '\n')
            f.write('Num de puntos(real): ' + str(len) + '\n')
            f.write('Time base scale: ' + str(timeB) + ' s'+ '\n')  
            f.write('Trigger (0.5PE): ' +str(trigger)+ ' v' +'\n')
            f.write('Tiempo de ejecucion: ' +str(round(((currentTime() - startTime)/60),2))+ ' min' +'\n')
            
        result=[timeB, str(len)]
    if(scope=='3'):

        trigger=float(rta.query(ds.lvlTriggerKey))
        #aRate=float(rta.query(ds.arateKey))
        sRate=float(rta.query(ds.srateKey))
        timeB=float(rta.query(ds.timeBaseKey))
        segPkey=float(rta.query(ds.segmentPKey))
        #timeB=5

        with open(path, 'w') as f:

            #f.write('ok')
            #f.write('Resolucion(real): ' + str(sRate) + " ! "+ str(aRate) + ' Sa/s'+ '\n')
            f.write('Resolucion(SRATE): ' + str(sRate) + ' Sa/s'+ '\n')
            f.write('Resolucion (real): '+str(len/(timeB*10))+' Sa/s'+ '\n')
            f.write('Puntos con SRATE: '+str(sRate*timeB*10)+ '\n')
            f.write('Num de puntos(real): ' + str(len) + '\n')
            f.write('Segment Puntos: '+str(segPkey)+ '\n')
            f.write('Time base scale: ' + str(timeB) + ' s'+ '\n')  
            f.write('Trigger (0.5PE): ' +str(trigger)+ ' v' +'\n')
            f.write('Tiempo de ejecucion: ' +str(round(((currentTime() - startTime)/60),2))+ ' min' +'\n')
        
        result=[timeB, str(len)]

        """ Hay que tener en cuenta que los valores coinciden cuando el osciloscopio tiene la barra donde aparece 
            la onda completa, si por ejemplo la reducimos a la mitad, hay valores que van a seguir devolviendo
            toda la onda completa y otros la coloreada en blanco"""

    return result

#Func generacion de ficheros (waveform)
def file_writer_wf(path, tsr, y, i):
    with open(path+"_"+str(i)+ ".txt", 'w') as f:
                f.write(str(tsr))
                f.write('\n')
                for i in range(len(y)):
                    f.write(str(round(y[i],5)))
                    f.write('\n')

#Func current time
def currentTime():
    return time.time()

#Func sleep
def waiting(device):
    opc = "0"
    while opc.strip() != "1":
        opc = device.query(ds.rdy)

#Func return instr segun dispositivo
def init_pyvisa(instr):
    rm = pyvisa.ResourceManager()
    if instr == "scope1":
        device = rm.open_resource('TCPIP::192.168.0.32::INSTR')
    if instr == "scope2":
        device = rm.open_resource('TCPIP::192.168.1.100::INSTR')
    if instr == "scope3":
        device = rm.open_resource('TCPIP::169.254.168.151::INSTR')
        #device = rm.open_resource('TCPIP0:KEYSIGH-MUTUU36::inst0::INSTR')
    if instr == "smu":
        device = rm.open_resource('TCPIP::169.254.216.252::INSTR')
    if instr == "arbGen":
        device = rm.open_resource('TCPIP::192.168.0.34::INSTR')
    if instr == "powerSupply":
        device = rm.open_resource('TCPIP::192.168.0.35::INSTR')
    return device

def file_writer_iv(vValues, iValues, path):
    listAux = np.arange(0 , len(vValues) , 1)

    #Escritura fichero
    with open(path + '.txt', 'a+') as f:
        for i in listAux:
            f.write(str(iValues[i]))
            f.write(' ')
            f.write(str(vValues[i]))
            f.write('\n')

    with open(path + '.txt', 'a+') as f:
        f.write('0 0\n')

def chronometter(startTime, t, self=None):
    while(round(((currentTime() - startTime)/60),2) < t):
        time.sleep(0.99)
        os.system('cls' if os.name == 'nt' else 'clear')
        min, sec = divmod((currentTime() - startTime), 60)
        #print(round(((currentTime() - startTime)/60),2))
        print(str(int(min)) + ":" + str(int(sec)))
        #self.update_idletasks()  # Actualizar la interfaz gráfica