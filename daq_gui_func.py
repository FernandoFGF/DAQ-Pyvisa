"""
Módulo para el manejo de operaciones del sistema operativo.

Este módulo importa y utiliza el módulo `os` para realizar diversas operaciones
relacionadas con el sistema operativo, como la manipulación de archivos y directorios,
el acceso a variables de entorno y otras funcionalidades relacionadas.

"""
import os
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib import colors
from scipy.signal import find_peaks
import dictionary_SCPI as ds
import time 
import threading



import lab_module as lm

def start_iv(self):
    """
    Realiza un barrido de voltaje y devuelve los valores medidos.
    Obtiene los valores ingresados en los campos de entrada: v_start, v_stop, v_step, option.
    Verifica si alguno de los campos está vacío.
    Imprime los valores de inicio, parada y paso de la barrida de voltaje.
    - Inicializa la fuente de medida.
    - Realiza la configuración necesaria para la barrida en modo escalón.
    - Inicia la transición y adquisición de datos.
    - Recupera los resultados de voltaje y corriente medidos.
    - Apaga la fuente de medida.
    - Realiza el manejo de datos y lectura, filtrando los valores de corriente.
    - Retorna los valores de voltaje y corriente medidos.
    """
    # Deshabilitar el botón Start
    self.start_button.configure(state="disabled")
    # Obtener los valores ingresados en los campos de entrada
    try:
        v_start = float(self.vStart.get()) if self.vStart.get() else 1.0
        v_stop = float(self.vStop.get()) if self.vStop.get() else -40.0
        v_step = float(self.vStep.get()) if self.vStep.get() else 0.05
    except ValueError:
        print("Error: Los valores ingresados deben ser números válidos.")
        self.start_button.configure(state="normal")
        return
    option = self.options.get()
    print(f"Starting sweep from {v_start}V to {v_stop}V at {v_step}V step")
    if option == "SMU":
        # No tocar/Configuración
        smu = lm.init_pyvisa("smu")
        del smu.timeout
        # Reset
        smu.write(ds.rst)
        # Configuración de barrido escalonado
        smu.write(ds.voltMode)
        smu.write(ds.sweepMode)
        smu.write(ds.sweepSing)
        smu.write(ds.sweepLin)
        smu.write(f":SOUR:VOLT:STAR {v_start}")
        smu.write(f":SOUR:VOLT:STOP {v_stop}")
        points = int(abs(v_start - v_stop) / v_step)  # Ahora usa floats
        smu.write(f":SOUR:VOLT:POIN {points}")
        # Configuración de medición de corriente en rango automático
        smu.write(ds.smuAuto1)
        smu.write(ds.smuAuto2)
        smu.write(ds.smuAuto3)
        # Generar disparos por algoritmo automático interno
        smu.write(ds.smuTrig)
        smu.write(f":trig:coun {points}")
        # Encender el interruptor de salida
        smu.write(ds.smuOn)
        # Iniciar transición y adquirir
        smu.write(ds.smuInit)
        lm.waiting(smu)
        # Recuperar resultados de medición
        i_result = smu.query(ds.queryCurr)
        i_values = i_result.split(",")
        i_values[-1] = i_values[-1].rstrip('\n')
        v_result = smu.query(ds.queryVolt)
        v_values = v_result.split(",")
        v_values[-1] = v_values[-1].rstrip('\n')
        smu.write(ds.smuOff)
        # Convertir la lista en una cadena separada por comas
        v_values = ', '.join(v_values)
        i_values = ', '.join(i_values)
        self.v_values_aux.set(v_values)
        self.i_values_aux.set(i_values)
    else:
        print("Not configured yet")


def save_results_iv(self, path):
    """
    Guarda los valores de voltaje y corriente en un archivo.

    :param path: Ruta del archivo donde se guardarán los resultados.
    """
    v_values = self.v_values_aux.get()
    i_values = self.i_values_aux.get()

    try:
        v_values = v_values.split()
        i_values = i_values.split()
        lm.file_writer_iv(v_values, i_values, path)
        print("Guardado con exito en: "+path)
    except Exception as e_error:
        print("Error al guardar. ", e_error)


def save_plot_as_png(self):
    """
    Guarda el gráfico actual como una imagen PNG.

    Utiliza el nombre proporcionado en el widget de entrada `save_entry`
    y guarda la imagen en la ubicación correspondiente a la pestaña actual
    en el formato "nombre.png". Si no se proporciona un nombre, se muestra
    un mensaje de error.
    """
    name = self.save_entry.get()
    path = lm.path(self.tabview.get())
    lm.create_dir(path)
    if not name:
        print("Introduzca un nombre antes de guardar.")
    else:
        filename = path + name + '.png'
        fig = self.canvas.figure
        fig.savefig(filename)
        print("Imagen guardada correctamente.")

def thread_spectrum(self):

    self.thread_spec_activo = True
    # Crear un hilo para ejecutar la función principal
    self.thread_spec = threading.Thread(target=start_spectrum, args=(self,))
    self.thread_spec.start()

    #self.stopSpec_button.configure(state="normal")

def start_spectrum(self):
    """
    Inicia la adquisición de datos del espectro.

    Esta función se activa al presionar el botón "Start". Realiza los siguientes pasos:
    - Deshabilita el botón "Start".
    - Obtiene el número de datos ingresados en el widget "entries".
    - Crea un lienzo (canvas) para mostrar el histograma.
    - Borra el histograma anterior.
    - Configura la comunicación con el instrumento y selecciona el canal especificado.
    - Genera los datos del espectro y actualiza el histograma cada 100 datos.
    - Al finalizar, habilita nuevamente el botón "Start", 
        actualiza los datos auxiliares y emite un sonido de confirmación.
    """
    if self.entries.get():

        try:
            # Deshabilitar el botón Start
            self.startSpec_button.configure(state="disabled")

            # Obtener el número de datos del entry self.entries
            num_datos = int(self.entries.get())

            # Crear un nuevo lienzo (canvas) y configurar el grid
            fig = Figure(figsize=(6, 4), dpi=100)
            self.ax = fig.add_subplot(111)

            # Borrar el histograma anterior
            self.ax.clear()

            self.canvas = FigureCanvasTkAgg(fig, self.liveplot)
            self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
            self.ax.set_xlabel("Charge(Vs)")

            # Datos y contadores para el histograma
            x_values = []

            scope=self.selected_scopeSpec.get()
            rta = lm.init_pyvisa("scope"+scope)
            del rta.timeout

            # Generar los datos aleatorios y actualizar el histograma
            for i in range(1, num_datos + 1):

                if(scope=='1'):
                    rta.write("FORM BIN")
                    channel = self.selected_channelSpec.get()
                    #print(ds.selectChanCur(channel))
                    rta.write(ds.selectChanCur(channel))
                    if rta.query(ds.rdy):
                        p_1 = float(rta.query(ds.posC1))
                    if rta.query(ds.rdy):
                        p_2 = float(rta.query(ds.posC2))

                    r_r = p_1-p_2

                if(scope=='2'):
                    rta.write("FORM BIN")
                    channel = self.selected_channelSpec.get()
                    #print(ds.selectChanCur(channel))
                    rta.write(ds.selectChanCur(channel))
                    r_r = float(rta.query('MEAS1:RES:ACT? '))

                if(scope=='3'):
                    rta.write(ds.headerOff)
                    rta.write(ds.currmeasKey)
                    r_r = float(rta.query(ds.resultKey))

                x_values.append(r_r)

                # Print de control
                lm.counter_finish(len(x_values), num_datos)
                if len(x_values) == 0:
                    break
                self.update_idletasks()  # Actualizar la interfaz gráfica

                if i % 100 == 0:
                    self.ax.clear()  
                    self.ax.hist(x_values, bins=50)
                    # Print de control
                    #lm.counter_finish(len(x_values), num_datos)
                    # Actualizar la imagen
                    self.canvas.draw()
                    self.update_idletasks()  # Actualizar la interfaz gráfica
                #time.sleep(0.01)
            self.hist_data.set(x_values)
            rta.close()

        except Exception as e_error:
            print("Error:", e_error)

        finally:
            # Habilitar el botón Start nuevamente al finalizar
            self.startSpec_button.configure(state="normal")
            self.values_aux.set(" ".join(map(str, x_values)))
            lm.beep()
            print("Finish histogram.")
    else:
        print("Introduce un valor para entries primero.")

def open_results(self):
    """
    Abre la carpeta de resultados.

    Esta función se activa al presionar el botón "Open Results". Realiza los siguientes pasos:
    - Obtiene la ruta de la carpeta de resultados según la pestaña seleccionada.
    - Reemplaza "/" por "\" en la ruta para que sea compatible con Windows.
    - Imprime la ruta obtenida para verificar.
    - Verifica si la carpeta existe.
    - Abre una nueva ventana del explorador de archivos en la carpeta de resultados.
    """
    path = lm.path(self.tabview.get())
    try:
        path = path.replace("/", "\\")
        print("Ruta obtenida:", path[:-1])  # Imprimir la ruta obtenida

        # Verificar si la carpeta existe
        if not os.path.isdir(path[:-1]):
            raise Exception("La ruta especificada no existe o no es una carpeta.")

        # La carpeta existe, abrir una nueva ventana
        os.system(f'explorer "{path[:-1]}"')
    except Exception as e_error:
        print("Error al abrir la carpeta:", e_error)


def save_results_spec(self, path, name):
    """
    Guarda los resultados del espectro en un archivo de texto.
    Esta función recibe la ruta `path` y el nombre `name` para
        guardar los resultados en un archivo de texto.
    Realiza los siguientes pasos:
    - Obtiene los valores del espectro de la variable `values_aux` en el objeto `self`.
    - Convierte los valores a números flotantes.
    - Crea un rango auxiliar `aux_len` de acuerdo a la longitud de los valores.
    - Abre un archivo de texto en modo escritura en la ruta `path` con el nombre `name.txt`.
    - Escribe en el archivo el valor mínimo y máximo de los valores del espectro en una línea.
    - Escribe en el archivo los valores del espectro separados por espacios en una línea.
    - Imprime un mensaje de éxito al guardar los resultados en la ruta especificada.
    """
    valuep = self.values_aux.get()
    # Convertir los valores a números
    valuep = [float(val) for val in valuep.split()]
    aux_len = np.arange(0, len(valuep), 1)
    try:
        with open(path + name + '.txt', 'w', encoding='utf-8') as f_ile:
            f_ile.write(str(np.min(valuep)) + " " + str(np.max(valuep)) + "\n")
            for i in aux_len:
                f_ile.write(str(valuep[i])+" ")
                # f.write('\n')
        print("Guardado con exito en: "+path)
    except Exception as e_error:
        print("Error al guardar.", e_error)


def save_results(self):
    """
    Guarda los resultados de acuerdo a la pestaña activa.

    Esta función guarda los resultados según la pestaña activa en el programa GUI.
    Realiza los siguientes pasos:
    - Obtiene el nombre del archivo de la variable `save_entry` en el objeto `self`.
    - Obtiene la ruta de la pestaña activa del objeto `tabview` utilizando la función `lm.path()`.
    - Si no se proporciona un nombre de archivo, imprime un mensaje de advertencia.
    - De lo contrario, crea el directorio correspondiente a la ruta
         si no existe utilizando la función `lm.create_dir()`.
    - Si la pestaña activa es "IV Curves", 
        guarda los resultados llamando a la función `save_results_iv()`.
    - Si la pestaña activa es "Spectrum", 
        guarda los resultados llamando a la función `save_results_spec()`.
    - Si la pestaña activa es "Waveform", 
        imprime un mensaje indicando que esta función se guarda automáticamente.
    """
    name = self.save_entry.get()
    path = lm.path(self.tabview.get())
    if not name:
        print("Introduzca un nombre antes de guardar.")
    else:
        lm.create_dir(path)
        if self.tabview.get() == "IV Curves":
            path = path + name
            save_results_iv(self, path)
        if self.tabview.get() == "Spectrum":
            save_results_spec(self, path, name)
        if self.tabview.get() == "Waveform":
            print("Esta funcion se guarda automaticamente")


def plot_example_spec(self):
    """
    Ejemplo de trazado de un histograma.

    Esta función muestra un ejemplo de trazado de un histograma utilizando la biblioteca Matplotlib.
    Realiza los siguientes pasos:
    - Crea una figura con el tamaño y la resolución especificados.
    - Añade un eje a la figura.
    - Define los datos `y` para el histograma.
    - Traza el histograma utilizando el método `hist()` del eje.
    - Crea un objeto `FigureCanvasTkAgg` para mostrar la figura en la interfaz gráfica.
    - Dibuja la figura en el lienzo.
    - Coloca el widget del lienzo en la cuadrícula de la interfaz gráfica.
    """
    fig = Figure(figsize=(6, 4), dpi=100)

    a_x = fig.add_subplot(111)

    y_y = [1, 2, 3, 4, 5]
    a_x.set_xlabel("Charge(Vs)")
    a_x.hist(y_y)

    self.canvas = FigureCanvasTkAgg(fig, self.liveplot)
    self.canvas.draw()
    self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")


def plot_example_wf(self):
    """
    Ejemplo de trazado de una forma de onda.

    Esta función muestra un ejemplo de trazado de una forma de onda.
    Realiza los siguientes pasos:
    - Crea una figura con el tamaño y la resolución especificados.
    - Añade un eje a la figura.
    - Define los datos `x` e `y` para la forma de onda.
    - Traza la forma de onda utilizando el método `plot()` del eje.
    - Crea un objeto `FigureCanvasTkAgg` para mostrar la figura en la interfaz gráfica.
    - Dibuja la figura en el lienzo.
    - Coloca el widget del lienzo en la cuadrícula de la interfaz gráfica.
    """
    fig = Figure(figsize=(6, 4), dpi=100)
    a_x = fig.add_subplot(111)

    x_x = [1, 2, 3, 4, 5]
    y_y = [10, 10, 50, 40, 10]

    a_x.plot(x_x, y_y)

    self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
    self.canvas.draw()
    self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")


def plot_example_iv(self):
    """
    Ejemplo de trazado de una curva IV.

    Esta función muestra un ejemplo de trazado de una curva de corriente-voltaje.
    Realiza los siguientes pasos:
    - Crea una figura con el tamaño y la resolución especificados.
    - Añade un eje a la figura.
    - Define los datos `x` e `y` para la curva IV.
    - Traza la curva utilizando el método `plot()` del eje.
    - Crea un objeto `FigureCanvasTkAgg` para mostrar la figura en la interfaz gráfica.
    - Dibuja la figura en el lienzo.
    - Coloca el widget del lienzo en la cuadrícula de la interfaz gráfica.
    """
    fig = Figure(figsize=(6, 4), dpi=100)
    a_x = fig.add_subplot(111)

    x_x = [1, 2, 3, 4, 5]
    y_y = [2, 4, 6, 8, 10]

    # Agregar etiquetas de ejes
    a_x.set_xlabel('Voltios')
    a_x.set_ylabel('Amperios')

    a_x.plot(x_x, y_y)

    self.canvas = FigureCanvasTkAgg(fig, self.plotIV)
    self.canvas.draw()
    self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

def start_vbr(self, vbr_output):
    """
    Iniciar el cálculo de Vbr.

    Esta función realiza los siguientes pasos para calcular el punto de máxima tangencia (Vbr):
    - Habilita la edición del widget `vbr_output`.
    - Borra el contenido del widget `vbr_output`.
    - Obtiene los valores de tensión (`v_values`) e intensidad (`i_values`).
    - Si no se proporcionan valores de tensión o intensidad, imprime un mensaje de error.
    - De lo contrario, convierte los valores a listas de tipo float.
    - Filtra los valores negativos de `v_values` e `i_values` para obtener las seccion negativa.
    - Si no hay valores negativos, imprime un mensaje de error.
    - De lo contrario, actualiza `v_values` e `i_values` con las secciones negativas.
    - Calcula las derivadas de `i_values` respecto a `v_values`.
    - Encuentra el índice de la máxima tangente en la derivada.
    - Obtiene las coordenadas del punto de máxima tangencia (max_x, max_y).
    - Inserta el valor de `max_x` en el widget `vbr_output`.
    - Deshabilita la edición del widget `vbr_output`.
    - Obtiene la figura y el lienzo del gráfico.
    - Limpia el eje actual del gráfico.
    - Traza la curva IV en el gráfico.
    - Traza un punto rojo en el punto de máxima tangencia.
    - Actualiza la figura para mostrar los cambios.

    Args:
        vbr_output: Widget de salida para mostrar el valor de Vbr.
    """
    vbr_output.configure(state="normal")
    vbr_output.delete("1.0", "end")
    # Asignar un valor a la variable
    v_values = self.v_values_aux.get()
    i_values = self.i_values_aux.get()


    if not v_values or not i_values:
        print("Necesitas realizar algun analisis primero..")
    else:
        # Dividir la cadena en elementos individuales
        v_values = v_values.split(', ')
        i_values = i_values.split(', ')
        # Convertir cada elemento a float
        v_values = [float(x) for x in v_values]
        i_values = [float(x) for x in i_values]
        #print(v_values)
        # Quedarse con los valores negativos
        x_negativas = [valor_x for valor_x, valor_y in zip(
            v_values, i_values) if valor_x < -0.01]
        y_negativas = [valor_y for valor_x, valor_y in zip(
            v_values, i_values) if valor_x < -0.01]

        # print(y_negativas)

        if not x_negativas or not y_negativas:
            print("No se encuentran valore adecuados para calcular Vbr.")
        else:

            v_values = x_negativas
            i_values = y_negativas

            
            # Convertir i_values en un arreglo NumPy
            i_values = np.array(i_values)

            # Sustituir valores menores que 1e-8 por 1e-8
            i_values = np.where(i_values > -1e-7, -1e-7, i_values)

            #print(i_values)


            #Calculamos derivada de intensidad, dividimos I'/I y buscamos el maximo.
            dydx = np.diff(i_values) / np.diff(v_values)

            # Encontrar el índice del valor máximo
            max_i = np.argmax(i_values)

            # Eliminar el valor máximo del arreglo
            i_values = np.delete(i_values, max_i)

            dydx_over_y = dydx/i_values

            # Encontrar el índice de la máxima tangente
            max_index = np.argmin(dydx_over_y)

            # Obtener el punto de máxima tangencia
            max_x = v_values[max_index]
            max_y = i_values[max_index]

            vbr_output.insert("0.0", str(max_x)+" V")
            vbr_output.configure(state="disabled")
            # Obtener la figura y el lienzo
            fig = self.canvas.figure

            # Dibujar el punto rojo en el lienzo
            self.canvas.draw()
            a_x = fig.gca()
            a_x.cla()
            a_x.set_xlabel('Voltios')
            a_x.set_ylabel('Amperios')
            a_x.plot(x_negativas, y_negativas)
            a_x.plot(max_x, max_y, 'ro')

            #a_x.plot(v_values[1:], dydx_over_y)
            # Crear un segundo eje y (derecho)
            ax2 = a_x.twinx()

            # Trazar la segunda serie de datos en el eje y secundario (derecho)
            ax2.plot(v_values[1:], dydx_over_y, 'r-')

            # Actualizar la figura
            fig.canvas.draw()


def start_qr(self, qr_output):
    """
    Iniciar el cálculo de Qr.

    Esta función realiza los siguientes pasos para calcular la resistencia de carga (Qr):
    - Habilita la edición del widget `qr_output`.
    - Borra el contenido del widget `qr_output`.
    - Obtiene los valores de tensión (`v_values`) e intensidad (`i_values`).
    - Si no se proporcionan valores de tensión o intensidad, imprime un mensaje de error.
    - De lo contrario, convierte los valores a listas de tipo float.
    - Filtra los valores positivos de `v_values` e `i_values` para obtener las seccion positiva.
    - Si no hay valores positivos, imprime un mensaje de error.
    - De lo contrario, actualiza `v_values` e `i_values` con las secciones positivas.
    - Filtra los valores de `v_values` e `i_values` que tienen una tensión menor o igual a 0.75V.
    - Calcula la pendiente `m` mediante la fórmula:
         (max(i_values) - min(i_values)) / (max(v_values) - min(v_values)).
    - Calcula la resistencia de carga `qr` como el inverso de `m`, redondeado a un decimal.
    - Inserta el valor de `qr` en el widget `qr_output`.
    - Deshabilita la edición del widget `qr_output`.
    - Obtiene la figura y el lienzo del gráfico.
    - Limpia el eje actual del gráfico.
    - Traza la curva IV en el gráfico.
    - Traza un punto rojo en los extremos de la línea recta que representa `qr`.
    - Actualiza la figura para mostrar los cambios.

    Args:
        qr_output: Widget de salida para mostrar el valor de Qr.
    """
    qr_output.configure(state="normal")
    qr_output.delete("1.0", "end")
    # Asignar un valor a la variable
    v_values = self.v_values_aux.get()
    i_values = self.i_values_aux.get()

    if not v_values or not i_values:
        print("Necesitas realizar algun analisis primero..")
    else:
        # Dividir la cadena en elementos individuales
        v_values = v_values.split(', ')
        i_values = i_values.split(', ')
        # Convertir cada elemento a float
        v_values = [float(x) for x in v_values]
        i_values = [float(x) for x in i_values]
        # Quedarse con los valores positivos
        x_positivas = [valor_x for valor_x, valor_y in zip(
            v_values, i_values) if valor_x > 0.01]
        y_positivas = [valor_y for valor_x, valor_y in zip(
            v_values, i_values) if valor_x > 0.01]

        # print(y_positivas)

        if not x_positivas or not y_positivas:
            print("No se encuentran valore adecuados para calcular Qr.")
        else:
            v_values = [valor_x for valor_x, valor_y in zip(
                x_positivas, y_positivas) if valor_x > 0.75]
            i_values = [valor_y for valor_x, valor_y in zip(
                x_positivas, y_positivas) if valor_x > 0.75]
            #print(i_values)
            #print(v_values)

            # Calcular de QR ...
            m_m = (max(i_values)-min(i_values))/(max(v_values)-min(v_values))
            q_r = f'{round(1/m_m, 1):.1f}'

            qr_output.insert("0.0", str(q_r)+" Ω")
            qr_output.configure(state="disabled")
            # Obtener la figura y el lienzo
            fig = self.canvas.figure

            # Dibujar el ajuste recto en el lienzo
            self.canvas.draw()
            a_x = fig.gca()
            a_x.cla()
            a_x.set_xlabel('Voltios')
            a_x.set_ylabel('Amperios')
            a_x.plot(x_positivas, y_positivas)
            x_values = [min(v_values), max(v_values)]
            y_values = [min(i_values), max(i_values)]
            a_x.plot(x_values, y_values, 'ro', linestyle="--")

            # Actualizar la figura
            fig.canvas.draw()


def complete(self):
    """
    Completes the plotting of the voltage-current data.

    Retrieves the voltage and current values from the input fields,
    converts them to float values, and plots the data on the canvas.

    If no voltage or current values are provided, a message is printed.

    """
    # Asignar un valor a la variable
    v_values = self.v_values_aux.get()
    i_values = self.i_values_aux.get()
    if not v_values or not i_values:
        print("Necesitas realizar algun analisis primero..")
    else:
        # Dividir la cadena en elementos individuales
        v_values = v_values.split(', ')
        i_values = i_values.split(', ')
        # Convertir cada elemento a float
        #print(v_values)
        v_values = [float(x) for x in v_values]
        i_values = [float(x) for x in i_values]
        # Obtener la figura y el lienzo
        fig = self.canvas.figure

        # Dibujar el ajuste recto en el lienzo
        self.canvas.draw()
        a_x = fig.gca()
        a_x.cla()
        a_x.set_xlabel('Voltios')
        a_x.set_ylabel('Amperios')
        a_x.plot(v_values, i_values)

        # Actualizar la figura
        fig.canvas.draw()


def finding_peaks(self):
    """
    Finds and plots the peaks in the histogram data.

    Retrieves the histogram data from the input field, cleans it,
    and plots the histogram along with the identified peaks.

    If no histogram data is provided, a message is printed.

    """
    values = self.hist_data.get()
    if not values:
        print("Primero debes de recoger datos que analizar.")
    else:
        # Eliminar paréntesis y espacios en blanco
        values = values.replace("(", "").replace(")", "").replace(" ", "")
        values_list = values.split(",")
        data = np.array([float(x) for x in values_list])

        # Limpiar el plot existente sin crear un nuevo lienzo
        self.ax.clear()

        # Histograma
        n_n, bins, patches = self.ax.hist(data, bins=50)

        fracs = n_n / n_n.max()

        norm = colors.Normalize(fracs.min(), fracs.max())

        for thisfrac, thispatch in zip(fracs, patches):
            color = plt.cm.viridis(norm(thisfrac))
            thispatch.set_facecolor(color)

        # Plot de líneas
        bins = bins[1:]
        self.ax.plot(bins, n_n)

        # Encontrar los picos
        peaks, _ = find_peaks(n_n, prominence=80)
        # print(peaks)

        # Plot de los picos como marcadores "x"
        self.ax.plot(bins[peaks], n_n[peaks], "rx")

        # Actualizar la imagen
        self.canvas.draw()
        self.update_idletasks()  # Actualizar la interfaz gráfica

def thread_wf(self):
    # Crear un hilo para ejecutar la función principal
    thread_wf = threading.Thread(target=start_wf, args=(self,))
    thread_wf.start()

def start_wf(self):
    """
    Starts the waveform acquisition process.

    Retrieves the user input for time entries and file name.
    Creates directories based on dates and names.
    Initializes the instrument session and retrieves waveform data.
    Saves the waveform data to a file and updates the progress.
    Plots the waveform data on a canvas.
    Updates the slider range based on the number of files.

    """
    entries = self.timeWf.get()
    if not entries:
        entries=0

    if not self.save_entry.get():
        print("Introduce un nombre al fichero")

    else:
        name = self.save_entry.get()
        # Creacion de directorios por fechas y nombres
        path = lm.path("Waveform")
        lm.create_dir(path)
        path_d = path +"/" + name
        print(path_d)
        lm.delete_dir(path_d)
        lm.create_dir(path_d)
        path_f = path_d + "/" + name
        lm.delete_dir(path_f)
        start_time = lm.currentTime()
        lm.chronometter(start_time, float(entries), self)
        try:
            # rta=lm.init_pyvisa(lm.return_instr("scope"))
            scope=self.selected_scopeWf.get()
            rta = lm.init_pyvisa("scope"+scope)

        except Exception as ex:
            print('Error initializing the instrument session:\n' + ex.args[0])
            exit()
        self.update_idletasks()
        rta.timeout=20000
        if (scope == "3"):
            rta.write(":STOP")
            #rta.write(ds.lsbfKey)
            rta.write(ds.asciiKey)
            #rta.write(":ACQuire:SEGMented:TTAGs ON")
            #rta.write(":WAV:SOURCE CHAN2")
            rta.write(ds.channelKey(self.selected_channelWf.get()))
            #print(ds.channelKey(self.selected_channelWf.get()))
            trigg = rta.query(ds.numCountsKey)
            prev_tsr = None  # Variable para almacenar el TSR anterior
            #trigg=1
            #rta.write(ds.modeSegment)
            for i in range(int(trigg)):
            #for i in range(1):

                rta.write(ds.selectCurrKey(trigg, i+1))
                #rta.write(":ACQuire:SEGMented:INDex 7")
                #rta.clear()
                #lm.waiting(rta)

                y_aux = rta.query(ds.waveformkey)
                lm.waiting(rta)


                # Limpiar y procesar los datos
                raw_data_cleaned = y_aux.strip()  # Eliminar espacios en blanco al inicio y final
                raw_data_cleaned = raw_data_cleaned.replace('\n', '').replace('\r', '')  # Eliminar saltos de línea
                raw_data_list = raw_data_cleaned.split(',')  # Dividir en una lista por comas

                # Filtrar elementos vacíos o inválidos y convertir a flotantes
                y_y = [float(x) for x in raw_data_list if x.strip()]

                tsr = rta.query(":WAVeform:SEGMented:TTAG?")

                # Si el TSR actual es igual al anterior, salir del bucle
                if tsr == prev_tsr:
                    print("TSR repetido, terminando el bucle.")
                    break
        
                prev_tsr = tsr  # Actualizar el TSR previo
                
                lm.file_writer_wf(path_f, tsr, y_y, i)
                lm.counter_finish(i, trigg)
                self.update_idletasks()  # Actualizar la interfaz gráfica
        else:
            rta.write("STOP")
            rta.write(ds.ascii)
            rta.write(ds.lsbf)
            trigg = rta.query(ds.numCounts)
            if(scope == "2"):
                rta.write(ds.openHist(scope))
        
            for i in range(int(trigg)):

                rta.write(ds.selectCurr(trigg, i))
                y_aux = rta.query(ds.waveform(self.selected_channelWf.get()))
                # print(y_aux)
                y_y = [float(i) for i in y_aux.split(',')]

                lm.waiting(rta)

                tsr = rta.query(ds.tsr)  #esto

                lm.file_writer_wf(path_f, tsr, y_y, i)
                lm.counter_finish(i, trigg)
                self.update_idletasks()  # Actualizar la interfaz gráfica
        print("100%")
        print("Finish waveform.")
        path_fd = path_d + "/DATA.txt"
        lm.delete_dir(path_fd)
        [time_base, num_points]=lm.create_data(path_fd, rta, start_time, len(y_y), scope)
        lm.create_zip(path_d, name)
        self.path_wf.set(path_d)
        self.num_points.set(num_points)

        rta.close()
        lm.beep()

        if(scope=="3"):
            x_x = np.linspace(0, time_base*10, len(y_y))
        else:
            x_x = np.linspace(0, time_base*12, len(y_y))

        # Crear un nuevo lienzo (canvas) y configurar el grid
        fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = fig.add_subplot(111)

        # Borrar el histograma anterior
        self.ax.clear()

        self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Plot de los nuevos datos
        self.ax.plot(x_x, y_y)

        # Configuración del gráfico
        self.ax.set_xlabel('Time(S)')
        self.ax.set_ylabel('Voltaje(V)')

        # Actualizar la figura
        fig.canvas.draw()

        [count,time]=count_files(self)

        self.slider_wf.configure(to=count-1, number_of_steps=count-1)

def count_files(self):
    """
    Counts the number of files with a specific prefix in a folder.

    Retrieves the path of the folder containing the files.
    Retrieves the prefix from the user input.
    Counts the files in the folder that have the specified prefix.
    Returns the count of files.

    """
    # Ruta de la carpeta
    path = self.path_wf.get()

    # Obtener la lista de archivos en la carpeta
    files = os.listdir(path)

    # Contar los archivos con el prefijo deseado
    count = sum(1 for file in files if file.startswith(
        str(self.save_entry.get())+"_"))
    
    path=path+"/"+str(self.save_entry.get())+"_0.txt"
    
    with open(path, 'r') as archivo:
        time = archivo.readline()

    result=[count, time]

    return result


def start_dcr(self, dcr_output):
    """
    Calculates and displays the DCR (Data Collection Rate) based on the number of files
    and the specified time interval.

    Retrieves the output field for displaying the DCR.
    Clears the output field and prepares it for new content.
    Calculates the DCR by dividing the number of files by the specified time interval in minutes.
    Displays the calculated DCR in the output field.
    If an error occurs during the calculation, prints an error message.
    Disables the output field.

    """
    dcr_output.configure(state="normal")
    dcr_output.delete("1.0", "end")

    [num_files, time_files]=count_files(self)

    try:
        dcr = round(num_files/(-float(time_files)), 2)
        dcr_output.insert("0.0", str(dcr)+" Hz")
    except Exception as e_error:
        print("Error al calcular el dcr:", e_error)

    dcr_output.configure(state="disabled")


def slider_event(self, value):
    """
    Event handler for the slider.

    Retrieves the selected file based on the slider value.
    Reads the data from the selected file.
    Creates data points for the plot.
    Creates a new canvas and configures the grid.
    Clears the previous plot.
    Plots the new data on the graph.
    Configures the graph settings.
    Updates the figure.

    """
    print("Fichero n: "+ str(round(value)))
    
    path = str(self.path_wf.get())+"/"+str(self.save_entry.get()) + \
        "_"+str(round(value))+".txt"

    with open(path, 'r', encoding='utf-8') as file:
        lines = file.readlines()[2:]  # Saltar las dos primeras líneas

    data = [float(line.strip()) for line in lines]

    # Crear los puntos para el gráfico con 3752 valores
    x_x = np.linspace(0, 1000, int(self.num_points.get()))

    # Crear un nuevo lienzo (canvas) y configurar el grid
    fig = Figure(figsize=(6, 4), dpi=100)
    self.ax = fig.add_subplot(111)

    # Borrar el histograma anterior
    self.ax.clear()

    self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
    self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

    # Plot de los nuevos datos
    self.ax.plot(x_x, data)

    # Configuración del gráfico
    self.ax.set_xlabel('Time(S)')
    self.ax.set_ylabel('Voltage(V)')

    # Actualizar la figura
    fig.canvas.draw()


def decrease_slider_value(self):
    """
    Decreases the value of the slider by 1.
    Retrieves the selected file based on the new slider value.
    Reads the data from the selected file.
    Creates data points for the plot.
    Creates a new canvas and configures the grid.
    Clears the previous plot.
    Plots the new data on the graph.
    Configures the graph settings.
    Updates the figure.

    """
    current_value = round(self.slider_wf.get())
    if current_value > 0:
        new_value = current_value - 1
        self.slider_wf.set(new_value)
        print("Fichero n: "+ str(int(self.slider_wf.get())))
        path = str(self.path_wf.get())+"/"+str(self.save_entry.get()) + \
            "_"+str(round(self.slider_wf.get()))+".txt"

        with open(path, 'r', encoding='utf-8') as file:
            lines = file.readlines()[2:]  # Saltar las dos primeras líneas

        data = [float(line.strip()) for line in lines]

        # Crear los puntos para el gráfico con 3752 valores
        x_x = np.linspace(0, 1000, int(self.num_points.get()))

        # Crear un nuevo lienzo (canvas) y configurar el grid
        fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = fig.add_subplot(111)

        # Borrar el histograma anterior
        self.ax.clear()

        self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Plot de los nuevos datos
        self.ax.plot(x_x, data)

        # Configuración del gráfico
        self.ax.set_xlabel('Time(S)')
        self.ax.set_ylabel('Voltage(V)')

        # Actualizar la figura
        fig.canvas.draw()


def increase_slider_value(self):
    """
    Increases the value of the slider by 1.
    Retrieves the current value of the slider.
    Retrieves the total count of files.
    Checks if the current value is less than the total count.
    Sets the new value of the slider.
    Prints the selected file number.
    Retrieves the path of the selected file.
    Reads the data from the selected file.
    Creates data points for the plot.
    Creates a new canvas and configures the grid.
    Clears the previous plot.
    Plots the new data on the graph.
    Configures the graph settings.
    Updates the figure.

    """
    current_value = round(self.slider_wf.get())
    [count, time]=count_files(self)
    if current_value < count:
        new_value = current_value + 1
        self.slider_wf.set(new_value)
        print("Fichero n: "+ str(int(self.slider_wf.get())))
        path = str(self.path_wf.get())+"/"+str(self.save_entry.get()) + \
            "_"+str(round(self.slider_wf.get()))+".txt"

        with open(path, 'r', encoding='utf-8') as file:
            lines = file.readlines()[2:]  # Saltar las dos primeras líneas

        data = [float(line.strip()) for line in lines]

        # Crear los puntos para el gráfico con 3752 valores
        x_x = np.linspace(0, 1000, int(self.num_points.get()))

        # Crear un nuevo lienzo (canvas) y configurar el grid
        fig = Figure(figsize=(6, 4), dpi=100)
        self.ax = fig.add_subplot(111)

        # Borrar el histograma anterior
        self.ax.clear()

        self.canvas = FigureCanvasTkAgg(fig, self.plot_wf)
        self.canvas.get_tk_widget().grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # Plot de los nuevos datos
        self.ax.plot(x_x, data)

        # Configuración del gráfico
        self.ax.set_xlabel('Time(S)')
        self.ax.set_ylabel('Voltage(V)')

        # Actualizar la figura
        fig.canvas.draw()
