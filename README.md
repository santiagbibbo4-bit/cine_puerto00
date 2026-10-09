# Cine de Cortos (Django)

Migración independiente del sitio Node/Express a Python + Django. La aplicación mantiene la estética original (CSS y JavaScript copiados a `cine/static/cine/`) y ofrece cartelera, ficha de programa, cortos, salas 2D/4D, tráiler, cuentas verificadas por email, reservas por grupo, QR y check-in de uso único.

No se modificó el proyecto Node fuente. Este proyecto puede ejecutarse por separado y no incluye pagos online.

## Requisitos

- Windows 10/11 y Python 3.10 o superior (Python 3.13 probado).
- VS Code con la extensión Python recomendada.
- PowerShell.

## Instalación y ejecución local (PowerShell)

Abrí `cine-cortos-python` en VS Code o ejecutá:

```powershell
cd C:\Users\santi\OneDrive\Desktop\centro\cine-cortos-python
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Si PowerShell bloquea la activación del entorno, podés ejecutar `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` y reemplazar `python` por `.\.venv\Scripts\python.exe` en los comandos siguientes. Abrí <http://127.0.0.1:8000/>; administración: <http://127.0.0.1:8000/admin/>.

En VS Code, abrí esta carpeta y seleccioná `.venv\Scripts\python.exe` con **Python: Select Interpreter** si no lo detecta automáticamente. Para iniciar el sitio, podés usar el terminal integrado con `python manage.py runserver`.

En desarrollo el email se imprime en la terminal. Para probar registro, copiá desde allí la ruta `/verificar-email/...` al navegador. La migración crea textos legales y datos de contacto de ejemplo/incompletos; revisalos en Administración antes de publicar.

Si olvidás la contraseña, desde **Ingresar** elegí **¿Olvidaste tu contraseña?** y seguí el enlace que se envía al email de la cuenta. Con la sesión iniciada, también podés cambiarla desde **Cambiar contraseña** en el menú.

## Cargar cartelera

Ingresá a `/admin/` con una cuenta de personal (`is_staff`):

1. Elegí **Agregar película o programa** y completá título, sinopsis, duración, clasificación, estreno, tráiler y afiche (archivo de hasta 5 MB o URL).
2. Agregá uno o varios cortometrajes en esa misma pantalla.
3. Para que aparezca en **Próximos estrenos**, elegí fecha futura y estado **Publicado**. Para que aparezca en **Cartelera**, agregá una o más funciones publicadas con fecha, horario, sala y capacidad. También podés marcarlo como **Destacado** para el carrusel de Inicio.
4. En **Funciones y capacidad**, usá **Agregar otra función** para añadir todas las que necesites en el día. No se permiten dos funciones activas en la misma sala y horario; las salas 2D y 4D pueden funcionar en paralelo. El panel muestra cuántos lugares se reservaron de la capacidad total y no permite bajar la capacidad por debajo de las reservas existentes. Al completarse el cupo, la función aparece gris como agotada.
5. Para administrar ajustes y textos legales, entrá en **Administración avanzada de Django** desde el final del panel. Creá cuentas para el personal desde Usuarios y activá `is_staff`; limitá `is_superuser` a administradores de confianza.

Una función no aparece en Cartelera solo por publicar el programa: también tiene que existir al menos una función futura publicada. Los programas con fecha futura se muestran en Próximos estrenos; las funciones que cargues se muestran en Cartelera aunque la fecha de estreno del programa todavía sea futura.

La capacidad reservada se mantiene automáticamente y no se edita manualmente. Una reserva confirmada ocupa los lugares incluso después del check-in. El código/QR representa al grupo completo y solo permite un ingreso.

## Configuración

Copiá `.env.example` a `.env`; no publiques este último. Variables principales:

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `SITE_URL`.
- `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`.
- `DATABASE_PATH`, `MEDIA_ROOT`, `BOOKING_CUTOFF_MINUTES`, `MAX_TICKETS_PER_BOOKING`.

Para SMTP, usa `django.core.mail.backends.smtp.EmailBackend` en `EMAIL_BACKEND` y configura credenciales mediante variables de entorno. No guardes credenciales reales en Git.
Antes de producción, generá una clave con `python -c "import secrets; print(secrets.token_urlsafe(50))"` y reemplazá el valor de `DJANGO_SECRET_KEY` en `.env`; el servidor rechazará la clave de ejemplo o una clave corta si `DJANGO_DEBUG=0`.

## Pruebas

```powershell
python manage.py check
python manage.py test cine
```

Incluyen páginas públicas, verificación, control de capacidad/idempotencia, QR y autorización/check-in único.

## Despliegue (resumen)

1. Usá una base de datos persistente y respaldos (SQLite sirve para una instalación pequeña; considerá PostgreSQL para concurrencia/carga).
2. Configurá secretos y SMTP fuera del repositorio; `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` y `SITE_URL` con el dominio HTTPS real.
3. Ejecutá `python manage.py migrate`, `python manage.py collectstatic` y el chequeo `python manage.py check --deploy`.
4. Serví `cine.wsgi:application` con un servidor WSGI de producción detrás de HTTPS; serví estáticos y medios con el servidor/web storage apropiado. No uses `runserver` en producción.
5. Configurá proxy/HTTPS de forma correcta, rotación de logs, monitoreo y copias de seguridad. Verificá SMTP y el flujo completo de verificación y reservas.
6. Revisá textos legales, datos del cine, políticas de ingreso/cancelación, privacidad y obligaciones locales antes de habilitar el sitio.

El chequeo de despliegue puede advertir que HSTS para subdominios (`security.W005`) y precarga (`security.W021`) no están activados. Se dejaron sin activar deliberadamente: solo habilitalos cuando todos los subdominios sean HTTPS y el dominio cumpla las condiciones de precarga, para evitar bloquear sitios que no controlás.

## Alcance y seguridad

CSRF y sesiones Django están habilitados; contraseñas se validan y se almacenan con los hashers Django. La verificación usa enlaces aleatorios de corta duración y de un solo uso. Las consultas de datos de reservas están acotadas al usuario autenticado; el check-in requiere personal (`is_staff`). La reserva actualiza cupos dentro de transacción con una condición SQL atómica para no exceder la capacidad; los reintentos de formulario se protegen con clave idempotente.

Privacidad y términos se inicializan explícitamente como **borradores no revisados**. No son asesoramiento legal ni deben publicarse sin completar y revisar. Esta versión no procesa pagos, selección de asientos ni cancelaciones iniciadas por clientes.
