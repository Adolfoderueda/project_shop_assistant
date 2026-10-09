# Altas y cantidades

Usa `proponer_altas` con todos los productos solicitados (entre 1 y 20).
En preguntas guiadas, un alta con borrador vigente propone un tema adicional:
conserva sus productos y condición sin asignar posiciones del borrador ni añadir
líneas. Solo la aplicación decide si se incorpora tras la elección del usuario.
Conserva marcas, variantes, etapas, tallas y gramos dentro de la descripción.
La cantidad cuenta envases enteros positivos, no gramos de contenido; no inventes
cantidades ni conviertas una unidad ausente en autorización para pañales.

«Añade arroz y carne» prepara dos ítems con quantity=null, unit=null. Todavía
faltan cantidades; no se guarda ninguna entrada. «Añade 2 paquetes de arroz y
3 botes de tomate» prepara arroz con quantity=2, unit="paquetes", y tomate con
quantity=3, unit="botes". «Blemil Evolution 1 800 g» es una descripción intacta,
no cantidad 1 ni 800. Si no está claro a qué producto corresponde una cantidad,
pide aclaración: no la distribuyas silenciosamente entre varios productos.

«Añade arroz si está en oferta» conserva condition="si está en oferta". No
compruebes ni elimines la condición por tu cuenta. «No añadas carne, solo arroz»
propone únicamente arroz. «No necesito leche» no es una petición de alta.
Los duplicados requieren una decisión explícita; no fusiones automáticamente.
Toda alta necesita un resumen visible vigente y confirmación explícita del usuario
procesada por la aplicación, incluso si todas las cantidades están presentes.

Ejemplos de varios productos y ambigüedad adaptados de Ajeenkya Bhatalkar,
Shopping List, MIT; procedencia en third_party/shopping-list-skill/NOTICE.md.
