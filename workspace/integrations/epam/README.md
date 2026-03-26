# 🏛️ Integración EPAM - Consulta Ciudadana

## Descripción
Integración con la API pública de **EPAM** (Empresa Pública Aguas de Manta) que permite consultar datos demográficos del **Registro Civil ecuatoriano** mediante número de cédula.

## Endpoint
```
GET http://consultas.epam.gob.ec:3001/consultar?identificacion={CEDULA}
```

## Autenticación
- **Ninguna** - API pública sin autenticación

## Ejemplo de Consulta
```
http://consultas.epam.gob.ec:3001/consultar?identificacion=1313835231
```

## Estructura de Respuesta
```json
{
  "paquete": {
    "numeroPaquete": "5375",
    "entidades": {
      "entidad": [
        {
          "nombre": "Datos Demográficos (Registro Civil)",
          "filas": {
            "fila": [
              {
                "columnas": {
                  "columna": [
                    {"campo": "cedula", "valor": "1313835231"},
                    {"campo": "nombre", "valor": "GOMEZ CALDERON ISRAEL JULIO"},
                    {"campo": "fechaNacimiento", "valor": "04/10/1993"},
                    {"campo": "lugarNacimiento", "valor": "MANABI/MANTA/MANTA"},
                    {"campo": "estadoCivil", "valor": "SOLTERO"},
                    {"campo": "profesion", "valor": "INGENIERO"},
                    {"campo": "condicionCiudadano", "valor": "CIUDADANO"},
                    {"campo": "fechaExpedicion", "valor": "14/07/2021"},
                    {"campo": "fechaExpiracion", "valor": "14/07/2031"}
                  ]
                }
              }
            ]
          }
        }
      ]
    }
  }
}
```

## Campos Disponibles

| Campo | Descripción |
|---|---|
| `cedula` | Número de cédula |
| `nombre` | Nombre completo (APELLIDOS NOMBRES) |
| `fechaNacimiento` | Fecha de nacimiento |
| `lugarNacimiento` | Provincia/Cantón/Parroquia |
| `estadoCivil` | Estado civil |
| `conyuge` | Cónyuge |
| `profesion` | Profesión |
| `condicionCiudadano` | Condición ciudadana |
| `fechaExpedicion` | Expedición de cédula |
| `fechaExpiracion` | Expiración de cédula |
| `actaDefuncion` | Acta de defunción (0 = vivo) |
| `fechaDefuncion` | Fecha de defunción |

## Flujo de Consulta en MaxAgno
1. El usuario solicita consultar una cédula
2. MaxAgno construye la URL: `http://consultas.epam.gob.ec:3001/consultar?identificacion={CEDULA}`
3. Usa `tavily_extract` para obtener la respuesta JSON
4. Parsea los datos de `paquete.entidades.entidad[0].filas.fila[0].columnas.columna[]`
5. Presenta la información formateada al usuario