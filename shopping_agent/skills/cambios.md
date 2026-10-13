# Cambios e incrementos

## Construir los argumentos

Para una modificación de filas guardadas, identifica `kind`, `query` y la cantidad
**expresada por el usuario** antes de resolver candidatos. Si especifica un número
de envases/paquetes, `quantity` lleva ese número y `unit` la unidad indicada.
Estos campos se conservan aunque falte seleccionar origen o su cantidad base sea
desconocida: la aplicación resuelve la selección y hace la aritmética después.
Si el número no está expresado, `quantity` queda pendiente, no se inventa.

En `increment`, quantity es el adicional solicitado. En `set_quantity` y `replace`,
quantity es el total solicitado para la salida. `replace` incluye también
`replacement`. Ejemplo: sustituir leche entera por cuatro envases de leche de avena:
```json
{"kind":"replace","query":"leche entera","replacement":"leche de avena","quantity":4,"unit":"envases"}
```

Usa `proponer_cambio`: kind="increment" suma una cantidad adicional;
kind="set_quantity" propone un total explícito; kind="replace" necesita query
del producto de origen y replacement del destino. No confundas total con delta.
Conserva marcas, variantes, etapas, tallas y gramos. Mantén las condiciones como
condition; una negación no concede permiso para modificar ni borrar.

«Añade 2 paquetes más de arroz» propone un incremento de 2 paquetes, no un total
de 2. La aplicación calcula base, delta y total. Si desconoce la base, no la
supongas. «Deja arroz en 3 paquetes» propone un total de 3 paquetes.
«Sustituye leche entera por leche de avena» propone una sustitución, no dos altas.
No inventes una cantidad para el destino.

Si «leche» coincide con leche entera y leche de avena, pregunta cuál y utiliza
la selección de candidatos de la propuesta. No elijas una variante por parecido.
Si no hay coincidencia, pide aclaración; no inventes una referencia guardada.
Toda modificación permanece pendiente hasta el resumen visible y confirmación
explícita que valida la aplicación. Nunca afirmes que un borrador está guardado.

Ejemplo de leche entera/avena adaptado de referencias/commands.md de Shopping
List, Ajeenkya Bhatalkar, MIT; atribución completa en NOTICE.md.
