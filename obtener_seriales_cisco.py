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
            salida,
            flags=re.IGNORECASE,
        )

        for serial_encontrado in seriales:
            if valor_serial_valido(serial_encontrado):
                return serial_encontrado.strip()

        return None

    palabras_principales = (
        "chassis",
        "router",
        "switch",
        "system",
    )

    for elemento in inventario:
        texto = (
            elemento["name"]
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

    for patron in patrones:
        coincidencia = re.search(
            patron,
            salida,
            flags=re.IGNORECASE,
        )

        if coincidencia:
            serial = coincidencia.group(1).strip()

            if valor_serial_valido(serial):
                return serial

    return None


def obtener_serial(
    direccion_ip,
    usuario,
    contrasena,
    secreto_enable="",
):
    """
    Se conecta por SSH al equipo Cisco y obtiene su serial.
    """
    dispositivo = {
        "device_type": "cisco_ios",
        "host": direccion_ip,
        "username": usuario,
        "password": contrasena,
        "secret": secreto_enable,
        "port": 22,
        "conn_timeout": 15,
        "auth_timeout": 15,
        "banner_timeout": 20,
        "timeout": 30,
        "fast_cli": False,
    }

    conexion = None

    try:
        print("[CONECTANDO] " + direccion_ip)

        conexion = ConnectHandler(**dispositivo)

        if secreto_enable:
            conexion.enable()

        try:
            conexion.send_command(
                "terminal length 0",
                read_timeout=15,
            )
        except Exception:
            pass

        salida_inventario = conexion.send_command(
            "show inventory",
            read_timeout=45,
        )

        serial = extraer_serial_show_inventory(
            salida_inventario
        )

        if serial:
            print(
                "[CORRECTO] {} - Serial: {}".format(
                    direccion_ip,
                    serial,
                )
            )

            return {
                "ip": direccion_ip,
                "serial": serial,
                "estado": "Correcto - show inventory",
            }

        print(
            "[INFO] {}: consultando show version".format(
                direccion_ip
            )
        )

        salida_version = conexion.send_command(
            "show version",
            read_timeout=45,
        )

        serial = extraer_serial_show_version(
            salida_version
        )

        if serial:
            print(
                "[CORRECTO] {} - Serial: {}".format(
                    direccion_ip,
                    serial,
                )
            )

            return {
                "ip": direccion_ip,
                "serial": serial,
                "estado": "Correcto - show version",
            }

        return {
            "ip": direccion_ip,
            "serial": "",
            "estado": (
                "Conexion correcta, pero no se encontro el serial"
            ),
        }

    except NetmikoAuthenticationException:
        print(
            "[ERROR] {}: autenticacion SSH incorrecta".format(
                direccion_ip
            )
        )

        return {
            "ip": direccion_ip,
            "serial": "",
            "estado": "Error de autenticacion SSH",
        }

    except NetmikoTimeoutException:
        print(
            "[ERROR] {}: tiempo de conexion SSH agotado".format(
                direccion_ip
            )
        )

        return {
            "ip": direccion_ip,
            "serial": "",
            "estado": "Tiempo de conexion SSH agotado",
        }

    except Exception as error:
        mensaje = str(error).replace("\n", " ").strip()

        print(
            "[ERROR] {}: {}".format(
                direccion_ip,
                mensaje,
            )
        )

        return {
            "ip": direccion_ip,
            "serial": "",
            "estado": "Error: " + mensaje,
        }

    finally:
        if conexion is not None:
            try:
                conexion.disconnect()
            except Exception:
                pass


def crear_archivo_excel(resultados, ruta_salida):
    """
    Crea el Excel con las columnas IP, Serial y Estado.
    """
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Seriales Cisco"

    hoja.append(
        [
            "IP",
            "Serial",
            "Estado",
        ]
    )

    color_encabezado = PatternFill(
        fill_type="solid",
        fgColor="1F4E78",
    )

    fuente_encabezado = Font(
        color="FFFFFF",
        bold=True,
    )

    filas_encabezado = hoja.iter_rows(
        min_row=1,
        max_row=1,
        min_col=1,
        max_col=3,
    )

    for fila in filas_encabezado:
        for celda in fila:
            celda.fill = color_encabezado
            celda.font = fuente_encabezado
            celda.alignment = Alignment(
                horizontal="center",
                vertical="center",
            )

    for resultado in resultados:
        hoja.append(
            [
                resultado["ip"],
                resultado["serial"],
                resultado["estado"],
            ]
        )

    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    hoja.column_dimensions["A"].width = 18
    hoja.column_dimensions["B"].width = 25
    hoja.column_dimensions["C"].width = 65

    for fila in hoja.iter_rows(min_row=2):
        for celda in fila:
            celda.alignment = Alignment(
                vertical="top",
                wrap_text=True,
            )

    libro.save(ruta_salida)


def obtener_argumentos():
    """
    Obtiene los argumentos de línea de comandos.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Obtiene seriales de equipos Cisco por SSH "
            "y genera un archivo Excel."
        )
    )

    parser.add_argument(
        "-i",
        "--ips",
        default=NOMBRE_ARCHIVO_IPS,
    )

    parser.add_argument(
        "-o",
        "--output",
        default=NOMBRE_ARCHIVO_EXCEL,
    )

    return parser.parse_args()


def main():
    argumentos = obtener_argumentos()

    ruta_ips = resolver_ruta(argumentos.ips)
    ruta_excel = resolver_ruta(argumentos.output)

    print("=" * 70)
    print(" INVENTARIO DE SERIALES CISCO POR SSH")
    print("=" * 70)
    print(
        "Carpeta del programa : "
        + str(DIRECTORIO_PROGRAMA)
    )
    print(
        "Archivo de IP        : "
        + str(ruta_ips)
    )
    print(
        "Archivo de resultados: "
        + str(ruta_excel)
    )
    print("=" * 70)

    try:
        direcciones_ip = leer_direcciones_ip(
            ruta_ips
        )

    except (FileNotFoundError, OSError) as error:
        print("\n[ERROR] " + str(error))
        print(
            "Coloca ips.txt en la misma carpeta "
            "del ejecutable."
        )
        return 1

    if not direcciones_ip:
        print(
            "\n[ERROR] El archivo ips.txt "
            "no contiene IP validas."
        )
        return 1

    print(
        "\nSe encontraron {} direcciones IP validas.\n".format(
            len(direcciones_ip)
        )
    )

    usuario = input("Usuario SSH: ").strip()

    if not usuario:
        print(
            "[ERROR] El usuario no puede estar vacio."
        )
        return 1

    contrasena = getpass.getpass(
        "Contrasena SSH: "
    )

    if not contrasena:
        print(
            "[ERROR] La contrasena no puede estar vacia."
        )
        return 1

    secreto_enable = getpass.getpass(
        "Contrasena enable opcional; "
        "presiona Enter para omitir: "
    )

    resultados = []
    total = len(direcciones_ip)

    for posicion, direccion_ip in enumerate(
        direcciones_ip,
        start=1,
    ):
        print(
            "\n--- Equipo {} de {}: {} ---".format(
                posicion,
                total,
                direccion_ip,
            )
        )

        resultado = obtener_serial(
            direccion_ip,
            usuario,
            contrasena,
            secreto_enable,
        )

        resultados.append(resultado)

    try:
        crear_archivo_excel(
            resultados,
            ruta_excel,
        )

    except PermissionError:
        print(
            "\n[ERROR] Cierra seriales_cisco.xlsx "
            "antes de volver a ejecutar."
        )
        return 1

    except OSError as error:
        print(
            "\n[ERROR] No se pudo crear el Excel: "
            + str(error)
        )
        return 1

    correctos = sum(
        1
        for resultado in resultados
        if resultado["serial"]
    )

    print("\n" + "=" * 70)
    print(" PROCESO FINALIZADO")
    print("=" * 70)
    print(
        "Equipos procesados : {}".format(
            len(resultados)
        )
    )
    print(
        "Seriales obtenidos : {}".format(
            correctos
        )
    )
    print(
        "Sin serial o error : {}".format(
            len(resultados) - correctos
        )
    )
    print(
        "Archivo generado   : "
        + str(ruta_excel.resolve())
    )

    return 0


def ejecutar_programa():
    """
    Ejecuta el programa y registra errores inesperados.
    """
    try:
        return main()

    except KeyboardInterrupt:
        print(
            "\nProceso cancelado por el usuario."
        )
        return 130

    except Exception:
        detalle_error = traceback.format_exc()

        ruta_error = (
            DIRECTORIO_PROGRAMA
            / NOMBRE_ARCHIVO_ERROR
        )

        try:
            ruta_error.write_text(
                detalle_error,
                encoding="utf-8",
            )
        except OSError:
            pass

        print("\nERROR INESPERADO\n")
        print(detalle_error)
        print(
            "Detalle guardado en: "
            + str(ruta_error)
        )

        return 1


if __name__ == "__main__":
    codigo_salida = ejecutar_programa()
    pausar_programa()
    sys.exit(codigo_salida)
