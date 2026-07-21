#!/usr/bin/env python3

import argparse
import getpass
import ipaddress
import re
import sys
import traceback
from pathlib import Path

from netmiko import ConnectHandler
from netmiko.exceptions import (
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


NOMBRE_ARCHIVO_IPS = "ips.txt"
NOMBRE_ARCHIVO_EXCEL = "seriales_cisco.xlsx"
NOMBRE_ARCHIVO_ERROR = "error_programa.log"


def obtener_directorio_programa():
    """
    Obtiene la carpeta del archivo Python o del ejecutable.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


DIRECTORIO_PROGRAMA = obtener_directorio_programa()


def resolver_ruta(nombre_archivo):
    """
    Resuelve una ruta relativa usando como base la carpeta del programa.
    """
    ruta = Path(nombre_archivo)

    if ruta.is_absolute():
        return ruta

    return DIRECTORIO_PROGRAMA / ruta


def pausar_programa():
    """
    Evita que la ventana se cierre automáticamente.
    """
    try:
        input("\nPresiona Enter para cerrar el programa...")
    except (EOFError, KeyboardInterrupt):
        pass


def leer_direcciones_ip(ruta_archivo):
    """
    Lee el archivo de direcciones IP.

    Ignora:
    - Líneas vacías.
    - Comentarios que comiencen con #.
    - IP duplicadas.
    """
    if not ruta_archivo.exists():
        raise FileNotFoundError(
            "No se encontro el archivo de direcciones IP: "
            + str(ruta_archivo.resolve())
        )

    direcciones = []
    direcciones_vistas = set()

    with ruta_archivo.open("r", encoding="utf-8-sig") as archivo:
        for numero_linea, linea in enumerate(archivo, start=1):
            contenido = linea.split("#", maxsplit=1)[0].strip()

            if not contenido:
                continue

            try:
                ipaddress.ip_address(contenido)
            except ValueError:
                print(
                    "[ADVERTENCIA] Linea {} ignorada. IP no valida: {}".format(
                        numero_linea,
                        contenido,
                    )
                )
                continue

            if contenido not in direcciones_vistas:
                direcciones.append(contenido)
                direcciones_vistas.add(contenido)

    return direcciones


def valor_serial_valido(serial):
    """
    Valida que el serial no sea vacío o genérico.
    """
    if not serial:
        return False

    serial_normalizado = serial.strip().strip('"').upper()

    valores_no_validos = {
        "",
        "N/A",
        "NA",
        "NONE",
        "UNKNOWN",
        "NOT_SPECIFIED",
        "NOT SPECIFIED",
        "FFFFFFFFFFF",
    }

    return serial_normalizado not in valores_no_validos


def extraer_serial_show_inventory(salida):
    """
    Extrae el serial principal desde show inventory.
    """
    bloques = re.split(
        r'(?=NAME:\s*")',
        salida,
        flags=re.IGNORECASE,
    )

    inventario = []

    for bloque in bloques:
        nombre = re.search(
            r'NAME:\s*"([^"]+)"',
            bloque,
            flags=re.IGNORECASE,
        )

        descripcion = re.search(
            r'DESCR:\s*"([^"]+)"',
            bloque,
            flags=re.IGNORECASE,
        )

        pid = re.search(
            r"PID:\s*([^,\r\n]*)",
            bloque,
            flags=re.IGNORECASE,
        )

        serial = re.search(
            r"SN:\s*([^,\s\r\n]+)",
            bloque,
            flags=re.IGNORECASE,
        )

        if not serial:
            continue

        valor_serial = serial.group(1).strip().strip('"')

        if not valor_serial_valido(valor_serial):
            continue

        inventario.append(
            {
                "name": (
                    nombre.group(1).strip()
                    if nombre
                    else ""
                ),
                "description": (
                    descripcion.group(1).strip()
                    if descripcion
                    else ""
                ),
                "pid": (
                    pid.group(1).strip()
                    if pid
                    else ""
                ),
                "serial": valor_serial,
            }
        )

    if not inventario:
        seriales = re.findall(
            r"\bSN:\s*([A-Za-z0-9._/-]+)",
            s*lida,
            flags=re.IGNOREC*SE,
        )

        for serial_*ncontrado in seriales:
           *if valor_serial_valido(serial_enco*trado):
                return ser*al_encontrado.strip()

        ret*rn None

    palabras_principales * (
        "chassis",
        "rou*er",
        "switch",
        "sy*tem",
    )

    for elemento in i*ventario:
        texto = (
      *     elemento["name"]
            + " "
            + elemento["description"]
        ).lower()

        if any(
            palabra in texto
            for palabra in palabras_principales
        ):
            return elemento["serial"]

    return inventario[0]["serial"]


def extraer_serial_show_version(salida):
    """
    Extrae el serial desde diferentes formatos de show version.
    """
    patrones = [
        r"Processor board ID\s+([A-Za-z0-9._/-]+)",
        r"System serial number\s*:\s*([A-Za-z0-9._/-]+)",
        r"Chassis Serial Number\s*:\s*([A-Za-z0-9._/-]+)",
        r"Motherboard serial number\s*:\s*([A-Za-z0-9._/-]+)",
        r"Serial Number\s*:\s*([A-Za-z0-9._/-]+)",
    ]

   *for patron in patrones:
        co*ncidencia = re.search(
           *patron,
            salida,
      *     flags=re.IGNORECASE,
        *

        if coincidencia:
       *    serial = coincidencia.group(1)*strip()

            if valor_seri*l_valido(serial):
                *eturn serial

    return None


de* obtener_serial(
    direccion_ip,*    usuario,
    contrasena,
    s*creto_enable="",
):
    """
    Se*conecta por SSH al equipo Cisco y *btiene su serial.
    """
    disp*sitivo = {
        "device_type": *cisco_ios",
        "host": direcc*on_ip,
        "username": usuario*
        "password": contrasena,
 *      "secret": secreto_enable,
  *     "port": 22,
        "conn_tim*out": 15,
        "auth_timeout": *5,
        "banner_timeout": 20,
 *      "timeout": 30,
        "fast*cli": False,
    }

    conexion =*None

    try:
        print("[CONECTANDO] " + direccion_ip)

       *conexion = ConnectHandler(**dispos***vo)

        if secreto_enable:
***         conexion.enable()

    *** try:
            conexion.send_***mand(
                "terminal ***gth 0",
                read_tim***t=15,
            )
        exce***Exception:
            pass

   ***  salida_inventario = conexion.s***_command(
            "show inve***ry",
            read_timeout=45***       )

        serial = extra***serial_show_inventory(
         ***salida_inventario
        )

   ***  if serial:
            print(
***             "[CORRECTO] {} - Se***l: {}".format(
                 ***direccion_ip,
                  ***erial,
                )
       ***  )

            return {
      ***       "ip": direccion_ip,
     ***        "serial": serial,
      ***       "estado": "Correcto - sho***nventory",
            }

      ***rint(
            "[INFO] {}: co***ltando show version".format(
   ***          direccion_ip
         ***)
        )

        salida_vers*** = conexion.send_command(
      ***   "show version",
            r***_timeout=45,
        )

        ***ial = extraer_serial_show_versio***            salida_version
     ***)

        if serial:
          ***rint(
                "[CORRECTO] {} - Serial: {}".format(
        ***         direccion_ip,
         ***        serial,
                ***           )

            return***                "ip": direccion_***
                "serial": seria***                "estado": "Corre*** - show version",
            }
***      return {
            "ip":***reccion_ip,
            "serial"***",
            "estado": (
     ***        "Conexion correcta, pero*** se encontro el serial"
        *** ),
        }

    except Netmik***thenticationException:
        p***t(
            "[ERROR] {}: aute***cacion SSH incorrecta".format(
 ***            direccion_ip
       ***  )
        )

        return {
***         "ip": direccion_ip,
   ***      "serial": "",
            ***tado": "Error de autenticacion S***,
        }

    except NetmikoT***outException:
        print(
   ***      "[ERROR] {}: tiempo de con***on SSH agotado".format(
        ***     direccion_ip
            )
***     )

        return {
       ***  "ip": direccion_ip,
          ***serial": "",
            "estado***"Tiempo de conexion SSH agotado"***       }

    except Exception a***rror:
        mensaje = str(erro***replace("\n", " ").strip()

    *** print(
            "[ERROR] {}:***".format(
                direcc***_ip,
                mensaje,
  ***       )
        )

        retu***{
            "ip": direccion_ip***           "serial": "",
       ***  "estado": "Error: " + mensaje,***      }

    finally:
        if***nexion is not None:
            ***:
                conexion.disco***ct()
            except Exceptio***                pass


def crear***chivo_excel(resultados, ruta_sal***):
    """
    Crea el Excel con***s columnas IP, Serial y Estado.
*** """
    libro = Workbook()
    ***a = libro.active
    hoja.title ***Seriales Cisco"

    hoja.append***       [
            "IP",
            "Serial",
            "Estado",
        ]
    )

    color_enca***ado = PatternFill(
        fill_***e="solid",
        fgColor="1F4E***,
    )

    fuente_encabezado =***nt(
        color="FFFFFF",
    *** bold=True,
    )

    filas_enc***zado = hoja.iter_rows(
        m***row=1,
        max_row=1,
      ***in_col=1,
        max_col=3,
   ***
    for fila in filas_encabezad***        for celda in fila:
     ***    celda.fill = color_encabezad***           celda.font = fuente_e***bezado
            celda.alignme***= Alignment(
                hor***ntal="center",
                v***ical="center",
            )

  ***or resultado in resultados:
    *** hoja.append(
            [
                resultado["ip"],
                resultado["serial"],
                resultado["estado"],
            ]
        )

    hoja.fre***_panes = "A2"
    hoja.auto_filt***ref = hoja.dimensions

    hoja.***umn_dimensions["A"].width = 18
 ***hoja.column_dimensions["B"].widt*** 25
    hoja.column_dimensions["C"].width = 65

    for fila in hoj***ter_rows(min_row=2):
        for***lda in fila:
            celda.a***nment = Alignment(
             ***vertical="top",
                ***p_text=True,
            )

    ***ro.save(ruta_salida)


def obten***argumentos():
    """
    Obtien***os argumentos de línea de comand***
    """
    parser = argparse.A***mentParser(
        description=***           "Obtiene seriales de ***ipos Cisco por SSH "
           *** genera un archivo Excel."
     ***)
    )

    parser.add_argument***       "-i",
        "--ips",
  ***   default=NOMBRE_ARCHIVO_IPS,
 ***)

    parser.add_argument(
    *** "-o",
        "--output",
     ***default=NOMBRE_ARCHIVO_EXCEL,
  ***

    return parser.parse_args()***def main():
    argumentos = obt***r_argumentos()

    ruta_ips = r***lver_ruta(argumentos.ips)
    ru***excel = resolver_ruta(argumentos***tput)

    print("=" * 70)
    p***t(" INVENTARIO DE SERIALES CISCO***R SSH")
    print("=" * 70)
    ***nt(
        "Carpeta del program*** "
        + str(DIRECTORIO_PROG***A)
    )
    print(
        "Arc***o de IP        : "
        + str***ta_ips)
    )
    print(
       ***rchivo de resultados: "
        ***tr(ruta_excel)
    )
    print("**** 70)

    try:
        direccio***_ip = leer_direcciones_ip(
     ***    ruta_ips
        )

    exce***(FileNotFoundError, OSError) as ***or:
        print("\n[ERROR] " +***r(error))
        print(
       ***  "Coloca ips.txt en la misma ca***ta "
            "del ejecutable***        )
        return 1

    ***not direcciones_ip:
        prin***            "\n[ERROR] El archiv***ps.txt "
            "no contien***P validas."
        )
        re***n 1

    print(
        "\nSe en***traron {} direcciones IP validas***".format(
            len(direcc***es_ip)
        )
    )

    usua*** = input("Usuario SSH: ").strip(***    if not usuario:
        prin***            "[ERROR] El usuario ***puede estar vacio."
        )
  ***   return 1

    contrasena = ge***ss.getpass(
        "Contrasena ***: "
    )

    if not contrasena***       print(
            "[ERROR] La contrasena no puede estar vac***"
        )
        return 1

  ***ecreto_enable = getpass.getpass(***      "Contrasena enable opciona***"
        "presiona Enter para o***ir: "
    )

    resultados = []***  total = len(direcciones_ip)

 ***for posicion, direccion_ip in en***rate(
        direcciones_ip,
  ***   start=1,
    ):
        print***           "\n--- Equipo {} de {***{} ---".format(
                ***icion,
                total,
  ***           direccion_ip,
       ***  )
        )

        resultado***obtener_serial(
            dire***on_ip,
            usuario,
    ***     contrasena,
            sec***o_enable,
        )

        res***ados.append(resultado)

    try:***      crear_archivo_excel(
     ***    resultados,
            ruta***cel,
        )

    except Permi***onError:
        print(
        *** "\n[ERROR] Cierra seriales_cisc***lsx "
            "antes de volv***a ejecutar."
        )
        r***rn 1

    except OSError as erro***        print(
            "\n[ERROR] No se pudo crear el Excel: "
***         + str(error)
        )
***     return 1

    correctos = s***
        1
        for resultado*** resultados
        if resultado***erial"]
    )

    print("\n" + *** * 70)
    print(" PROCESO FINAL***DO")
    print("=" * 70)
    pri***
        "Equipos procesados : {***format(
            len(resultad***
        )
    )
    print(
    *** "Seriales obtenidos : {}".forma***            correctos
        )
*** )
    print(
        "Sin seria*** error : {}".format(
           ***n(resultados) - correctos
      ***
    )
    print(
        "Archi***generado   : "
        + str(rut***xcel.resolve())
    )

    retur***


def ejecutar_programa():
    ***
    Ejecuta el programa y regis*** errores inesperados.
    """
  ***ry:
        return main()

    e***pt KeyboardInterrupt:
        pr***(
            "\nProceso cancela***por el usuario."
        )
     ***return 130

    except Exception***       detalle_error = traceback***rmat_exc()

        ruta_error =***            DIRECTORIO_PROGRAMA
***         / NOMBRE_ARCHIVO_ERROR
***     )

        try:
           ***ta_error.write_text(
           ***  detalle_error,
               ***coding="utf-8",
            )
  ***   except OSError:
            p***

        print("\nERROR INESPER***\n")
        print(detalle_error***       print(
            "Detal***guardado en: "
            + str***ta_error)
        )

        ret*** 1


if __name__ == "__main__":
*** codigo_salida = ejecutar_progra***)
    pausar_programa()
    sys.***t(codigo_salida)
