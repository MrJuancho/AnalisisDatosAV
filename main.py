import requests
import json

import pandas as pd

from datetime import datetime
import os

from sklearn.preprocessing import minmax_scale
import numpy as np
from math import sqrt, log

# Define el nombre del archivo donde guardaremos la última fecha
filename = "last_check.txt"

def obtener_ultimafecha_revision():
    # Verifica si el archivo existe
    if os.path.isfile(filename):
        # Si existe, lee la última fecha registrada
        with open(filename, "r") as file:
            last_checked_date = file.read()
            return datetime.strptime(last_checked_date, '%Y-%m-%d %H:%M:%S.%f')
    else:
        # Si no existe, devuelve una fecha muy antigua
        return datetime.min

def actualizar_ultimafecha_revision():
    # Guarda la fecha y hora actual en el archivo
    with open(filename, "w") as file:
        file.write(str(datetime.now()))

def solicitud_API(metodo, url, cuerpo=None):
    # Declaración de los métodos permitidos
    metodos_permitidos = ['GET', 'POST', 'PUT', 'DELETE']

    # Verificación del método
    if metodo not in metodos_permitidos:
        print(f"Error: Método {metodo} no permitido. Los métodos permitidos son: {metodos_permitidos}")
        return None

    # Realización de la solicitud
    if metodo == 'GET':
        response = requests.get(url)

        # Manejo de la respuesta
        if response.status_code == 200:
            # Convierte la respuesta a un objeto de Python
            datos = json.loads(response.text)
            return datos
        else:
            print(f"Error al realizar la solicitud {metodo} a {url}: {response.status_code}")
            return None
    elif metodo == 'POST':
        response = requests.post(url, json=cuerpo)
    elif metodo == 'PUT':
        response = requests.put(url, json=cuerpo)
    elif metodo == 'DELETE':
        response = requests.delete(url)

def obtener_actividades(date):
    # Formatea la fecha a una cadena de texto para incluirla en la solicitud GET
    date_str = date.strftime('%Y-%m-%d %H:%M:%S.%f')  # ajusta esto al formato que la API espera

    # Haz una solicitud GET a la API
    actividades = solicitud_API('GET',f"http://pt-av.herokuapp.com/resultadoActividad/{date_str}")

    return actividades

def calcular_recompensa(idActividad, intentos, asistencia, tiempo):
    #ObtenerActividadAPI
    actividadResponse = solicitud_API('GET',f"http://pt-av.herokuapp.com/detalleActividad/{idActividad}")

    #Obtenemos los indices de la actividad
    indiceDificultad = actividadResponse["IndiceDificultad"]
    indiceMemoria = actividadResponse["IndiceMemoria"]
    indiceAtencion = actividadResponse["IndiceAtencion"]
    indicePercepcion = actividadResponse["IndicePercepcion"]

    #Transformacion del Tiempo a Segundos
    tiempo = datetime.strptime(tiempo,'%Y-%m-%dT%H:%M:%S.%fZ')

    # Extraer la hora, los minutos y los segundos
    hora = tiempo.hour
    minutos = tiempo.minute
    segundos = tiempo.second

    total_segundos = hora * 3600 + minutos * 60 + segundos

    #Normalizar los factores de Recompensa
    factoresRecompensa = [intentos, asistencia, total_segundos, indiceAtencion, indiceDificultad, indiceMemoria, indicePercepcion]
    factoresNormalizados = minmax_scale(factoresRecompensa, feature_range=(0, 1))

    # Los factores más bajos (menos intentos, menos tiempo, menos asistencias) se traducen en una recompensa más alta.
    # Los factores más altos (mayor dificultad, mayor interacción con habilidades) también se traducen en una recompensa más alta.
    recompensa = (1 - factoresNormalizados[0]) + (0.8 - factoresNormalizados[1]) + (1 - factoresNormalizados[2]) + \
              factoresNormalizados[3] + factoresNormalizados[4] + factoresNormalizados[5] + factoresNormalizados[6]

    return recompensa

def procesar_recompensas(actividades):
    # Procesamiento de actividades
    dfActividadesAlumno = pd.json_normalize(actividades) #Uso de pandas para procesar la informacion como DataFrame

    #Refactorizacion de nombre de Columnas
    dfActividadesAlumno = dfActividadesAlumno.rename(columns={
        "TblResultadosActividad_idResultadosAlumno":"idResultadoAlumno",
        "TblResultadosActividad_TiempoResolucion":"TiempoResolucion",
        "TblResultadosActividad_Intentos":"Intentos",
        "TblResultadosActividad_Asistencia":"Asistencias",
        "TblResultadosActividad_FechaRealizacion":"FechaRealizacion",
        "TblResultadosActividad_idAlumno":"idAlumno",
        "TblResultadosActividad_idActividad":"idActividad",
        "TblResultadosActividad_recompensa":"recompensa"
    })

    #Creamos Grupos por cada Resultados de alumno existentes
    dfAgrupados = dfActividadesAlumno.groupby('idAlumno')

    for idAlumno, grupoAlumno in dfAgrupados:
        print(">>>>>> CALCULO DE RECOMPENSAS <<<<<<")
        print(f"Alumno ID: {idAlumno}")
        print(grupoAlumno.to_string())
        print("\n---\n")  # Separador para hacerlo más legible

        for i, row in grupoAlumno.iterrows():

            resultados = row.to_dict()

            intentos = resultados["Intentos"]
            asistencias = resultados["Asistencias"]
            tResolucion = resultados["TiempoResolucion"]
            idActividad = resultados["idActividad"]

            idResultadoActividad = resultados["idResultadoAlumno"]

            recompensa = calcular_recompensa(idActividad,intentos,asistencias,tResolucion)

            solicitud_API('PUT',f"https://pt-av.herokuapp.com/resultadoActividad/{idResultadoActividad}",cuerpo={"idResultadoActividad":idResultadoActividad, "recompensaUCB":recompensa})

def procesar_actividades():
    #Obtenemos la API con las todas las actividades realizadas
    #Obtener Actividad API
    allResultadosActividades = solicitud_API('GET',"https://pt-av.herokuapp.com/resultadoActividad/")

    #Creamos el DataFrame de las actividades
    dfActividadesTotales = pd.json_normalize(allResultadosActividades)

    dfActividadesTotales.drop([
        'TblResultadosActividad_TiempoResolucion','TblResultadosActividad_Intentos',
        'TblResultadosActividad_Asistencia','TblResultadosActividad_FechaRealizacion'
    ], axis=1, inplace=True)

    dfActividadesTotales = dfActividadesTotales.rename(columns={
                "TblResultadosActividad_idResultadosAlumno":"idResultadoAlumno",
                "TblResultadosActividad_idAlumno":"idAlumno",
                "TblResultadosActividad_idActividad":"idActividad",
                "TblResultadosActividad_recompensa":"recompensa"
            })

    dfResultadosAlumno = dfActividadesTotales.groupby('idAlumno')

    for idAlumno, grupoAlumno in dfResultadosAlumno:
        print(">>>>>>> PROCESAMIENTO DE ACTIVIDADES <<<<<<<<")
        print(f"Alumno ID: {idAlumno}")
        print(grupoAlumno.to_string())
        print("\n---\n")  # Separador para hacerlo más legible

        indicesUCB = calcular_indices_UCB(grupoAlumno)

        for i, row in indicesUCB.iterrows():

            idActividad = row["idActividad"]
            print(row["idActividad"])
            print(idActividad)

            existencia = verificar_UCB_DB(idAlumno, idActividad)
            if existencia:
                solicitud_API('PUT',f"https://pt-av.herokuapp.com/indiceUCB/{idAlumno}",cuerpo={"idAlumno":idAlumno,"idActividad":idActividad,"indiceUCB":row['indice_UCB']})
            if not existencia:
                solicitud_API('POST',f"https://pt-av.herokuapp.com/indiceUCB",cuerpo={"idAlumno":idAlumno,"idActividad":idActividad,"indiceUCB":row['indice_UCB']})

def calcular_indices_UCB(dfActividadesAlumno):
    # Agrupa las actividades por ID de actividad y calcula la recompensa promedio y el número de veces que se realizó cada actividad.
    promedioActividades = dfActividadesAlumno.groupby('idActividad').agg({'recompensa': ['mean', 'count']}).reset_index()
    promedioActividades.columns = ['idActividad', 'recompensa_promedio', 'veces_realizada']

    # Calcula el índice UCB para cada actividad.
    total_activities = len(dfActividadesAlumno)
    promedioActividades['indice_UCB'] = promedioActividades['recompensa_promedio'] + np.sqrt((2 * np.log(total_activities)) / promedioActividades['veces_realizada'])

    return promedioActividades

def verificar_UCB_DB(idAlumno,idActividad):
    existencia = solicitud_API('GET',f"https://pt-av.herokuapp.com/indiceUCB/{idAlumno}")

    while True:
        if not existencia:
            print("No existe registro en la BD del indiceUCB de ese alumno")  # Si la lista está vacía, salimos del bucle
            return False
        else:
            print("Ya existen indices ucb para ese alumno")
            dfExistencia = pd.json_normalize(existencia)

            if idActividad in dfExistencia['TblIndiceUcbAlumno_idActividad'].values:
                return True
            else:
                return False

# Para usar estas funciones:
last_checked_date = obtener_ultimafecha_revision()
print("Última fecha de revisión:", last_checked_date)

# Obtener las nuevas actividades
new_activities = obtener_actividades(last_checked_date)
#print("Nuevas actividades:", new_activities)
while True:
    if not new_activities:
        print("No hay actividades por realizar")
        break
    else:
        procesar_recompensas(new_activities)
        #Calculo de Indices UCB
        procesar_actividades()
        break

# Y luego, después de revisar las nuevas actividades:
actualizar_ultimafecha_revision()