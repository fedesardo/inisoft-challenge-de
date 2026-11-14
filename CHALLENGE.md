# Challenge técnico — Data Engineering

Buscamos ver cómo encarás un problema de datos real y sucio: qué decidís y por
qué, cómo demostrás que el resultado es confiable, y cómo lo presentás.

Usá las herramientas que quieras, IA incluida. No hay un stack ni un flujo
correcto: nos interesa el tuyo.

**Tiempo estimado:** una jornada. Lo que no entre, listalo como fuera de alcance
con una línea de por qué.

## El caso

Un cliente de energía opera 40 equipos rotativos (bombas, compresores, turbinas)
en dos plantas. Manda un mes de telemetría (vibración y temperatura cada 15 min),
el maestro de equipos con los umbrales del fabricante y el export de órdenes de
trabajo (OT) de su sistema de mantenimiento.

La jefa de mantenimiento pide:

> *"Saber a cuáles equipos mandar a mantenimiento esta semana, y alguna razón
> para creerle a esa lista."*

Y aclara que el año pasado apagaron un sistema de alertas porque avisaba todo
el tiempo.

No hay diccionario de datos. `README-del-cliente.txt` tiene lo que recuerdan;
descubrir qué tienen realmente los archivos es parte del trabajo.

## Entregables

Un repositorio git con:

1. **Un pipeline que corra con un solo comando** y responda:
   - qué equipos mandar a mantenimiento al cierre de los datos, y por qué;
   - por qué creerle: evidencia de que el criterio habría anticipado las fallas
     del mes sin llenar de falsas alarmas. Cómo lo medís lo decidís vos.
2. **Un dashboard** para la jefa de mantenimiento. Simple, pero que comunique.
3. **Un README** que explique qué hace cada pieza y cómo correrlo.
4. **Un documento de decisiones**: qué asumiste, con qué evidencia, qué
   descartaste y por qué. Sumá una sección corta de **escalado**: qué cambia con
   500 equipos reportando cada minuto.
5. **Al menos 2 skills** para trabajar con estos datos: instrucciones
   reutilizables para un agente de IA, en el formato de tu herramienta
   (`SKILL.md` de Claude Code, rules de Cursor, etc.). Por ejemplo: cómo leer
   los archivos del sistema viejo y del nuevo. La prueba: con el drop del mes
   que viene, otra persona tiene que poder procesarlo con un agente usando tus
   skills. **Opcional:** la definición de un agente que sirva en la solución,
   por ejemplo un analista de datos que responda preguntas sobre el resultado.

## Los datos

```
drop/
  equipos.csv                   maestro y umbrales
  lecturas-2026-02-01.csv …     un archivo por día (30)
  ordenes-de-trabajo.csv        export del sistema de mantenimiento
  README-del-cliente.txt        nota del cliente
```

Unas 115.000 lecturas: entra en memoria en cualquier laptop.

## Restricciones

- **Un comando** levanta todo (`make run`, `docker compose up`, un script).
- **Sin cuentas cloud ni servicios pagos**, para que cualquiera del equipo pueda
  correrlo sin configurar nada. La producción va en la sección de escalado.
- **Si usás un LLM dentro del pipeline**, el comando tiene que funcionar sin API
  keys: un modelo local, o el resultado versionado con cómo regenerarlo.
- No hace falta mandar el historial de chat: alcanza con el repo y las decisiones.

## Después

Nos juntamos a conversar sobre la entrega: qué asumiste, qué descartaste, cómo
verificaste y cómo trabajaste, incluido el uso de IA y dónde tuviste que
corregirla.

**Dudas:** escribile a Mauro o a Julián como si fueran el cliente. Preguntar no
es obligatorio; si preferís asumir, dejalo escrito en las decisiones.
