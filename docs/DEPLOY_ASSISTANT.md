# Runbook — Asistente de draft en producción

Despliegue de los PRs **#81, #82 y #83** (el asistente de draft). #79 y #80 son
solo documentación.

Servidor: `dp-backup-ovh`, usuario `vpv`, raíz `/opt/vpv`. Backend uvicorn en
systemd (`vpv-backend`, venv en `/opt/vpv/backend/.venv`), frontend Next.js en
PM2 (`vpv-frontend`).

**No hay migraciones.** No cambia `package.json`. Lo único inhabitual es que el
backend estrena dos dependencias Python, así que esta vez **sí hace falta
`pip install`**.

Si algo sale mal, la sección 7 revierte en dos comandos: la feature nace
apagada, así que basta con no encenderla.

---

## 0. Antes de tocar el servidor: crear la API key

En `console.anthropic.com` (o `platform.openai.com`), crea una key **y ponle un
límite de gasto mensual**. El endpoint no tiene límite de consultas a propósito
—un tope que salta a mitad de un pick es peor que el gasto que evita— así que el
tope de la consola es el único freno de dinero. Con 10 $/mes vas sobrado: una
sesión de draft completa ronda los 5 $.

---

## 1. Código

```bash
cd /opt/vpv && git pull
```

Comprueba que ha llegado lo nuevo:

```bash
git log --oneline -1          # debe ser el merge del PR #83
ls backend/src/features/draft_assistant/
```

---

## 2. Dependencias del backend (paso nuevo)

`anthropic` y `openai` no estaban antes. Sin esto el backend arranca igual
(los imports son perezosos), pero la primera pregunta daría `ModuleNotFoundError`.

```bash
cd /opt/vpv/backend
.venv/bin/pip install -e .
```

Verifica:

```bash
.venv/bin/python -c "import anthropic, openai; print(anthropic.__version__, openai.__version__)"
```

Debe imprimir algo como `1.4.0 3.10.0`.

---

## 3. Configuración

Añade el bloque al final de `/opt/vpv/backend/.env`.

> **Ojo, esto muerde**: systemd arranca el backend con `EnvironmentFile=`, y
> systemd solo ignora los comentarios que están **en su propia línea**. Un
> `CLAVE=valor  # nota` mete el comentario dentro del valor. Escribe los
> comentarios en líneas aparte, como abajo. (El código ahora tolera el caso y
> recorta lo que va tras `#`, pero no te fíes: con una API key el resultado
> sería una key corrupta y un error críptico.)

**Pon las dos keys.** El chat trae un selector de proveedor y otro de modelo, y
solo ofrece los proveedores que tengan key. Con una sola key el selector no
aparece y siempre responde ese. `ASSISTANT_PROVIDER` y los `*_MODEL` son solo el
valor **por defecto** al abrir el panel; desde ahí se cambia sin tocar nada.

```bash
cat >> /opt/vpv/backend/.env <<'EOF'

# --- Asistente de draft ---
ASSISTANT_ENABLED=true
# Proveedor y modelos por defecto; el chat deja cambiarlos en caliente
ASSISTANT_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-PON-AQUI-LA-TUYA
OPENAI_API_KEY=sk-PON-AQUI-LA-TUYA
ASSISTANT_ANTHROPIC_MODEL=claude-opus-5
ASSISTANT_OPENAI_MODEL=gpt-5
ASSISTANT_ANONYMIZE_PARTICIPANTS=true
EOF
```

La lista de modelos del desplegable **se pide en vivo a cada proveedor**
(`models.list()`, cacheada 10 min), así que un modelo nuevo aparece solo, sin
tocar código. Si esa llamada falla, el desplegable se queda con el modelo por
defecto — nunca deja el chat sin funcionar.

Ajusta permisos si hiciera falta (el fichero lleva secretos):

```bash
chmod 600 /opt/vpv/backend/.env
ls -l /opt/vpv/backend/.env      # -rw------- vpv vpv
```

---

## 4. Build y reinicio

```bash
cd /opt/vpv/frontend && npm run build
pm2 restart vpv-frontend
sudo systemctl restart vpv-backend
```

`npm install` no hace falta: `package.json` no cambió. El `postbuild` copia
`public/` y `.next/static/` al output standalone, como siempre.

---

## 5. Verificación

**Backend arriba y sin errores de arranque:**

```bash
sudo systemctl status vpv-backend --no-pager
sudo journalctl -u vpv-backend -n 40 --no-pager
```

**La ruta existe:**

```bash
curl -s localhost:8000/openapi.json | grep -o '/draft-assistant/[^"]*'
```

Debe salir `/draft-assistant/{season_id}/{phase}/ask`.

**Está protegida (sin token debe rechazar):**

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  localhost:8000/api/draft-assistant/12/preseason/ask \
  -H 'Content-Type: application/json' -d '{"question":"hola"}'
```

Debe dar **401 o 403**, nunca 200.

**Prueba de verdad**: entra como admin en `/drafts/live/<id>`, despliega
**Asistente de draft** y pregunta *"¿a quién cojo en este pick?"*. Tarda 10-20 s
(dos o tres consultas al tablero antes de responder) y debajo de la respuesta
verás qué herramientas consultó. Si eso sale, está bien montado.

**Si la respuesta es un error de configuración**, el mensaje te dice cuál:
`Falta ANTHROPIC_API_KEY` o `ASSISTANT_PROVIDER no valido`. En el segundo caso,
mira si se coló un comentario inline en el `.env`.

---

## 6. Cambiar de proveedor o de modelo

**Desde el chat**, sin tocar el servidor: los dos selectores en la cabecera del
panel. Cada respuesta lleva debajo qué proveedor y modelo la generó, así que
puedes comparar en la misma conversación.

Para cambiar el **valor por defecto** al abrir el panel:

```bash
sed -i 's/^ASSISTANT_PROVIDER=.*/ASSISTANT_PROVIDER=openai/' /opt/vpv/backend/.env
sudo systemctl restart vpv-backend
```

Comprobar qué ofrece (como admin, con tu token):

```bash
curl -s localhost:8000/api/draft-assistant/providers -H "Authorization: Bearer $TOKEN" | head -c 500
```

---

## 7. Marcha atrás

**Apagarlo (lo normal, y suficiente):** el endpoint devuelve un 400 claro y el
panel deja de funcionar; el resto de la app no se entera.

```bash
sed -i 's/^ASSISTANT_ENABLED=.*/ASSISTANT_ENABLED=false/' /opt/vpv/backend/.env
sudo systemctl restart vpv-backend
```

**Revertir el código entero**, si hiciera falta:

```bash
cd /opt/vpv && git checkout 3ae96ab      # merge del PR #80, justo antes del asistente
cd frontend && npm run build && pm2 restart vpv-frontend
sudo systemctl restart vpv-backend
```

No hay que deshacer migraciones ni datos: la feature no escribe **nada** en la
base de datos.

---

## Qué esperar el día del draft

- **No hay límite de preguntas.** El freno de dinero es el tope de la consola.
- **Tarda 10-20 s por respuesta.** No hay streaming todavía; consulta el tablero
  dos o tres veces antes de contestar. Si eso molesta en vivo, es la primera
  mejora pendiente (§9 de `DRAFT_ASSISTANT.md`).
- **El tablero se cachea 60 s.** Si editas un tag y preguntas inmediatamente, el
  asistente puede ir un minuto por detrás. Quién está fichado, en cambio, se lee
  siempre en vivo: nunca te recomendará a alguien que acaban de coger.
- **No opina por su cuenta.** Si le pides que ordene el draft a su manera, se
  negará y te remitirá al tablero. Es a propósito.

---

## Prioridades reales antes del draft

Esto es lo último en la lista, no lo primero. Por delante van:

1. `sync-rosters 12` + `refresh-positions 12` — la ventana de escritura de
   posiciones se cierra en cuanto se scrapee la J4.
2. Rellenar los **tags** del tablero (es lo que más mueve el orden).
3. Cargar las **notas Marca/AS de J1–J3** cuando salgan.
4. Un **ensayo de draft real** (sin `?test=true`) y reset.

El asistente puede esperar; eso no.
