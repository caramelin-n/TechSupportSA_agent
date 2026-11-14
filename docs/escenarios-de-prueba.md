# Escenarios de prueba del agente — TechSupport S.A.

- Fecha: 2026-11-14 18:44
- Modelo: `gemini-3.5-flash-lite`
- Backend: http://localhost:8000
- Resultado: **13 de 13 escenarios OK**

| ID | Escenario | Requisitos | Resultado |
|---|---|---|---|
| E01 | Solicitud en texto claro | F01, F03, F05, F06, F07, F10 | ✅ |
| E02 | Captura de pantalla legible | F02, F03, F07 | ✅ |
| E03 | Captura borrosa | F02, F04 | ✅ |
| E04 | Log técnico largo | F02, F03, F07 | ✅ |
| E05 | Log ambiguo | F02, F04 | ✅ |
| E06 | Ticket duplicado | Criterio 10 | ✅ |
| E07 | Consultas de un usuario | F09 | ✅ |
| E08 | Consulta de soporte | F09 | ✅ |
| E09 | Permisos insuficientes | F10, criterio 11 | ✅ |
| E10 | Transición de estado inválida | F08, criterio 8 | ✅ |
| E11 | Gestión de un ticket e historial | F08, F10, F11, criterio 9 | ✅ |
| E12 | Confirmación rechazada | F06, F10 | ✅ |
| E13 | Resumen de incidencias | F12 | ✅ |

## E01. Solicitud en texto claro

**Requisitos:** F01, F03, F05, F06, F07, F10  
**Usuario:** Martín (usuario)  
**Qué se espera:** Con un mensaje informal pero completo, el agente clasifica, propone prioridad y crea el ticket después de la confirmación.

### Conversación

**Usuario:** Desde las 9 la impresora HP LaserJet del 3er piso no imprime para nadie de Compras. Los trabajos quedan en cola y no sale nada, y hoy tenemos que imprimir las órdenes de compra.

**Agente:**

> Antes de seguir necesito que confirmes:
> - Crear el ticket «Impresora HP LaserJet 3er piso no imprime para Compras» (categoría Hardware, prioridad Alta)

🔒 _Acción pendiente de confirmación:_ Crear el ticket «Impresora HP LaserJet 3er piso no imprime para Compras» (categoría Hardware, prioridad Alta)

**Decisión del usuario:** Aprueba

**Agente:**

> He registrado el ticket TCK-1014 con prioridad Alta y categoría Hardware para la impresora HP LaserJet del 3er piso. Quedó en estado Abierto y el equipo de soporte lo revisará a la brevedad debido a la urgencia con las órdenes de compra.

### Verificaciones

- ✅ Pide confirmación para `crear_ticket` — _acciones propuestas: crear_ticket_
- ✅ Se crea 1 ticket con categoría Hardware prioridad Media o Alta o Crítica — _TCK-1014 «Impresora HP LaserJet 3er piso no imprime para Compras» (Hardware, Alta)_

## E02. Captura de pantalla legible

**Requisitos:** F02, F03, F07  
**Usuario:** Martín (usuario)  
**Qué se espera:** El agente lee el código de error de la captura y lo usa en el ticket, que queda con la captura adjunta.

### Conversación

**Usuario:** No puedo abrir la carpeta de Contabilidad, me sale esto. _(adjunta: captura_acceso_denegado.png)_

**Agente:**

> Antes de seguir necesito que confirmes:
> - Crear el ticket «Error de acceso denegado en carpeta de Contabilidad» (categoría Accesos y permisos, prioridad Media, 1 adjunto(s))

🔒 _Acción pendiente de confirmación:_ Crear el ticket «Error de acceso denegado en carpeta de Contabilidad» (categoría Accesos y permisos, prioridad Media, 1 adjunto(s))

**Decisión del usuario:** Aprueba

**Agente:**

> He registrado el incidente bajo el ticket **TCK-1015** con prioridad Media y la categoría de Accesos y permisos, adjuntando la captura del error de acceso denegado. Un operador de soporte se encargará de revisar los permisos de la carpeta de Contabilidad.

### Verificaciones

- ✅ El agente menciona alguna de: «0x80070005» — _encontradas: 0x80070005_
- ✅ Se crea 1 ticket con categoría Accesos y permisos y archivo adjunto — _TCK-1015 «Error de acceso denegado en carpeta de Contabilidad» (Accesos y permisos, Media)_

## E03. Captura borrosa

**Requisitos:** F02, F04  
**Usuario:** Lucía (usuario)  
**Qué se espera:** Si la imagen no se puede leer, el agente lo dice y pregunta; no inventa un error ni crea el ticket.

### Conversación

**Usuario:** No me anda esto. _(adjunta: captura_borrosa.png)_

**Agente:**

> La imagen adjunta (`captura_borrosa.png`) se ve borrosa y no permite leer ningún mensaje de error ni identificar el sistema o aplicación que está fallando. 
>
> ¿Podrías aclararnos qué sistema o equipo estás intentando usar, qué mensaje de error te aparece exactamente o desde cuándo tenés este problema? Con esa información podremos ayudarte a registrar la incidencia.

### Verificaciones

- ✅ Pide información adicional — _hizo al menos una pregunta_
- ✅ No intenta `crear_ticket` — _no la propuso_
- ✅ No se crea ningún ticket — _no se creó ninguno_

## E04. Log técnico largo

**Requisitos:** F02, F03, F07  
**Usuario:** Carla (usuario)  
**Qué se espera:** De un log de cientos de líneas, el agente identifica el error principal (timeout contra la base) y crea el ticket con el log adjunto.

### Conversación

**Usuario:** La app de facturación se me cierra sola. Te paso el log. _(adjunta: app_facturacion.log)_

**Agente:**

> Antes de seguir necesito que confirmes:
> - Crear el ticket «La app de facturación se cierra por timeout de conexión a la base de datos» (categoría Sistemas y aplicaciones, prioridad Alta, 1 adjunto(s))

🔒 _Acción pendiente de confirmación:_ Crear el ticket «La app de facturación se cierra por timeout de conexión a la base de datos» (categoría Sistemas y aplicaciones, prioridad Alta, 1 adjunto(s))

**Decisión del usuario:** Aprueba

**Agente:**

> He registrado la incidencia bajo el ticket **TCK-1016** con estado **Abierto** y prioridad **Alta**, adjuntando el log provisto que muestra los errores de tiempo de espera al conectar con la base de datos `db-prod-01`.

### Verificaciones

- ✅ El agente menciona alguna de: «timeout» — _encontradas: timeout_
- ✅ Se crea 1 ticket y archivo adjunto — _TCK-1016 «La app de facturación se cierra por timeout de conexión a la base de datos» (Sistemas y aplicaciones, Alta)_

## E05. Log ambiguo

**Requisitos:** F02, F04  
**Usuario:** Martín (usuario)  
**Qué se espera:** Un log sin errores claros no alcanza para crear un ticket: el agente explica qué ve y pide más datos.

### Conversación

**Usuario:** Te paso este log, revisalo. _(adjunta: log_ambiguo.log)_

**Agente:**

> Revisé el log adjunto (`log_ambiguo.log`). 
>
> El archivo contiene principalmente registros informativos normales del **servicio de facturación (v2.3.1)** y una única advertencia (`WARN`):
> `2026-10-21 14:30:00 WARN Respuesta lenta sin detalle adicional`
>
> Como se trata de una advertencia aislada y no de un error crítico, no constituye por sí sola una incidencia que requiera un ticket. 
>
> ¿Estás experimentando algún problema de rendimiento o error específico con el servicio de facturación que deba registrar?

### Verificaciones

- ✅ Pide información adicional — _hizo al menos una pregunta_
- ✅ No intenta `crear_ticket` — _no la propuso_
- ✅ No se crea ningún ticket — _no se creó ninguno_

## E06. Ticket duplicado

**Requisitos:** Criterio 10  
**Usuario:** Lucía (usuario)  
**Qué se espera:** Lucía ya tiene abierto TCK-1001 por facturación. El agente lo encuentra con otras palabras y pregunta antes de crear otro.

### Conversación

**Usuario:** No me abre el sistema de facturación, queda la pantalla en blanco.

**Agente:**

> Encontré un ticket abierto muy parecido al tuyo: **TCK-1001** («Sistema de facturación no abre»), que actualmente está en progreso. 
>
> ¿Es esta la misma incidencia? Si querés, puedo agregar un comentario en ese ticket en lugar de crear uno nuevo.

### Verificaciones

- ✅ El agente menciona alguna de: «TCK-1001», «TCK-1007» — _encontradas: TCK-1001_
- ✅ No se crea ningún ticket — _no se creó ninguno_

## E07. Consultas de un usuario

**Requisitos:** F09  
**Usuario:** Lucía (usuario)  
**Qué se espera:** Consultas en lenguaje natural, incluso con el ID sin prefijo.

### Conversación

**Usuario:** ¿Cuál es el estado del ticket 1001?

**Agente:**

> El ticket TCK-1001 se encuentra actualmente en estado **En progreso**. 
>
> Aquí tenés los detalles principales:
> - **Título:** Sistema de facturación no abre
> - **Prioridad:** Alta
> - **Categoría:** Sistemas y aplicaciones
> - **Asignado a:** S001

**Usuario:** Mostrame los tickets que tengo abiertos.

**Agente:**

> Tenés 5 tickets sin resolver:
>
> 1. **TCK-1001** (En progreso - Alta): Sistema de facturación no abre
> 2. **TCK-1004** (Pendiente - Media): Impresora del 2do piso no responde
> 3. **TCK-1007** (Abierto - Alta): La app de facturas da error de timeout
> 4. **TCK-1010** (En revisión - Media): No puedo instalar la actualización del antivirus
> 5. **TCK-1013** (En progreso - Media): WiFi inestable en 2do piso

### Verificaciones

- ✅ El agente menciona alguna de: «En progreso» — _encontradas: En progreso_
- ✅ El agente menciona alguna de: «TCK-1007» — _encontradas: TCK-1007_
- ✅ No se crea ningún ticket — _no se creó ninguno_

## E08. Consulta de soporte

**Requisitos:** F09  
**Usuario:** Diego (soporte)  
**Qué se espera:** Soporte consulta las incidencias críticas sin resolver (TCK-1002 y TCK-1006).

### Conversación

**Usuario:** ¿Qué incidencias críticas siguen pendientes?

**Agente:**

> Actualmente hay dos incidencias críticas sin resolver:
>
> 1. **TCK-1002**
>    - **Título:** Sin internet en oficina de Ventas
>    - **Estado:** Abierto
>    - **Categoría:** Redes y conectividad
>    - **Asignado a:** S002
>
> 2. **TCK-1006**
>    - **Título:** Servidor caído, backup no completa
>    - **Estado:** En progreso
>    - **Categoría:** Infraestructura
>    - **Asignado a:** S002
>
> ¿Te gustaría consultar el detalle o agregar un comentario en alguno de ellos?

### Verificaciones

- ✅ El agente menciona todas de: «TCK-1002», «TCK-1006» — _encontradas: TCK-1002, TCK-1006_

## E09. Permisos insuficientes

**Requisitos:** F10, criterio 11  
**Usuario:** Lucía (usuario)  
**Qué se espera:** Un usuario no puede cerrar tickets: aunque lo pida (y apruebe), el estado no cambia.

### Conversación

**Usuario:** Cerrá el ticket TCK-1004, ya no lo necesito.

**Agente:**

> El ticket TCK-1004 se encuentra actualmente en estado **Pendiente**. 
>
> Según los procedimientos del sistema, para poder cerrarlo primero debe pasar por los estados de **En progreso** y **Resuelto**, antes de llegar a **Cerrado**. 
>
> ¿Deseás que avance el ticket a **En progreso** para iniciar el proceso de cierre?

### Verificaciones

- ✅ TCK-1004 queda con estado «Pendiente» — _status = Pendiente_

## E10. Transición de estado inválida

**Requisitos:** F08, criterio 8  
**Usuario:** Diego (soporte)  
**Qué se espera:** TCK-1002 está Abierto y no puede pasar directo a Resuelto: el estado no cambia.

### Conversación

**Usuario:** Pasá el TCK-1002 a Resuelto, ya quedó.

**Agente:**

> El ticket TCK-1002 se encuentra actualmente en estado **Abierto**. Según las reglas del sistema, para llegar al estado *Resuelto* primero debe pasar por el estado *En revisión* y luego por *En progreso*. No es posible saltar directamente de Abierto a Resuelto.
>
> ¿Querés que lo pasemos a *En revisión* para avanzar con el flujo?

### Verificaciones

- ✅ TCK-1002 queda con estado «Abierto» — _status = Abierto_

## E11. Gestión de un ticket e historial

**Requisitos:** F08, F10, F11, criterio 9  
**Usuario:** Diego (soporte)  
**Qué se espera:** Soporte toma un ticket: cambia el estado, se lo asigna y comenta. Todo queda en el historial con fecha y responsable.

### Conversación

**Usuario:** Tomo el TCK-1002: pasalo a En revisión, asignámelo a mí (S001) y agregá el comentario «Revisando el switch de Ventas».

**Agente:**

> Antes de seguir necesito que confirmes:
> - Cambiar el estado de TCK-1002 a «En revisión»
> - Asignar TCK-1002 a S001

🔒 _Acción pendiente de confirmación:_ Cambiar el estado de TCK-1002 a «En revisión»

🔒 _Acción pendiente de confirmación:_ Asignar TCK-1002 a S001

**Decisión del usuario:** Aprueba

**Agente:**

> He actualizado el ticket TCK-1002:
> - Estado cambiado a **En revisión**.
> - Asignado a **S001**.
> - Se agregó el comentario: «Revisando el switch de Ventas».

**Usuario:** Mostrame el historial del TCK-1002.

**Agente:**

> Este es el historial de eventos del ticket TCK-1002:
>
> - **2026-10-13 08:05**: Creación del ticket (estado: Abierto) por el solicitante U002.
> - **2026-10-13 08:06**: Se adjuntó el archivo `captura_navegador.png` por U002.
> - **Hoy**: Estado cambiado de Abierto a En revisión por S001.
> - **Hoy**: Asignación modificada de S002 a S001 por S001.
> - **Hoy**: Se agregó el comentario «Revisando el switch de Ventas» por S001.

### Verificaciones

- ✅ TCK-1002 queda con estado «En revisión» — _status = En revisión_
- ✅ TCK-1002 queda con responsable «S001» — _assignee_id = S001_
- ✅ El historial de TCK-1002 registra STATUS_CHANGED, ASSIGNED, COMMENT_ADDED — _todos registrados_

## E12. Confirmación rechazada

**Requisitos:** F06, F10  
**Usuario:** Diego (soporte)  
**Qué se espera:** Si el usuario rechaza la confirmación, el cambio no se aplica.

### Conversación

**Usuario:** Subile la prioridad del TCK-1008 a Crítica.

**Agente:**

> Antes de seguir necesito que confirmes:
> - Cambiar la prioridad de TCK-1008 a «Crítica»

🔒 _Acción pendiente de confirmación:_ Cambiar la prioridad de TCK-1008 a «Crítica»

**Decisión del usuario:** Rechaza: «No, mejor dejala como está.»

**Agente:**

> El usuario rechazó la solicitud de cambio de prioridad ("No, mejor dejala como está"). No se modificó la prioridad del ticket TCK-1008. ¿Hay algo más en lo que te pueda ayudar?

### Verificaciones

- ✅ Pide confirmación para `actualizar_prioridad` — _acciones propuestas: actualizar_prioridad_
- ✅ TCK-1008 queda con prioridad «Alta» — _priority = Alta_

## E13. Resumen de incidencias

**Requisitos:** F12  
**Usuario:** Raúl (admin)  
**Qué se espera:** El administrador pide un resumen agrupado por estado, categoría y prioridad.

### Conversación

**Usuario:** Haceme un resumen de las incidencias por estado, categoría y prioridad.

**Agente:**

> Aquí tenés el resumen actual de las incidencias en el sistema:
>
> Total de tickets: 16
>
> Por estado:
> - Abierto: 4
> - En revisión: 4
> - En progreso: 3
> - Pendiente: 2
> - Resuelto: 2
> - Cerrado: 1
>
> Por categoría:
> - Hardware: 3
> - Redes y conectividad: 3
> - Sistemas y aplicaciones: 3
> - Infraestructura: 2
> - Accesos y permisos: 2
> - Software: 2
> - Otros: 1
>
> Por prioridad:
> - Alta: 7
> - Media: 5
> - Crítica: 2
> - Baja: 2

### Verificaciones

- ✅ El agente menciona todas de: «En progreso», «Hardware», «Crítica» — _encontradas: En progreso, Hardware, Crítica_
