# Despliegue en la nube con un solo puerto

El `docker-compose.yml` de la raíz publica dos puertos: 8000 para la API y 8050 para el
tablero. Eso funciona en local, pero en una máquina de la nube obliga a abrir dos reglas en
el grupo de seguridad, y el navegador termina haciendo peticiones a un origen distinto del
que sirvió la página.

Esta carpeta trae la variante de un solo puerto: **nginx entrega el tablero y además
reenvía `/api/` y `/docs` al contenedor de la API**, todo por el 8050.

```bash
# en la máquina de la nube, desde la raíz del repositorio
docker compose -f docker-compose.yml -f deploy/docker-compose.cloud.yml up -d --build
```

Antes de levantarlo, `frontend/js/config.js` debe apuntar al mismo origen:

```js
apiBase: location.origin + "/api/v1",
```

Después queda:

- tablero → `http://<ip>:8050/`
- API     → `http://<ip>:8050/api/v1/...`
- Swagger → `http://<ip>:8050/docs`

Probado el 22/09/2026 en una instancia `t2.medium` con Ubuntu 24.04 del AWS Academy
Learner Lab: los tres registros demo de Sleep-EDFx se analizaron de punta a punta contra
esta configuración.
