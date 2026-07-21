# Inventario de seriales Cisco

Programa para conectarse por SSH a equipos Cisco, consultar el serial
del equipo y guardar el resultado en un archivo Excel.

## Archivos necesarios

Los siguientes archivos deben estar en la misma carpeta:

- `InventarioSerialesCisco.exe`
- `ips.txt`

## Formato de ips.txt

El archivo debe contener una dirección IP por línea.

Ejemplo:

```text
# Routers Cisco
192.168.1.1
192.168.1.2
10.10.10.1
