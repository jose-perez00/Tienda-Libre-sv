# Tienda Libre

Sitio web de comercio electrónico de demostración. Permite explorar el catálogo, registrarse e iniciar sesión, publicar productos y agregarlos al carrito.

## Alojamiento gratuito de prueba (Render)

El proyecto incluye `render.yaml` para desplegar el servidor Python como servicio gratuito. Para publicarlo, sube el proyecto a un repositorio de GitHub y en Render selecciona **New + → Blueprint**, conecta ese repositorio y confirma el servicio `tienda-libre-prueba`. Render asigna una dirección pública `onrender.com`. El plan gratuito suspende servicios tras 15 minutos sin tráfico y el primer acceso posterior puede tardar alrededor de un minuto. El disco local del servicio gratuito es temporal; los datos del navegador (carrito y productos de demostración) no se sincronizan con otros usuarios o dispositivos.

El registro y el inicio de sesión usan SQLite. El disco del plan gratuito es temporal, por lo que las cuentas de prueba pueden perderse cuando Render reinicie o reemplace el servicio. No cargues información real ni uses este despliegue para ventas reales. El acceso web a la base SQLite y a archivos de código está bloqueado. Los productos del catálogo y el carrito siguen guardándose en el navegador, por lo que no se comparten entre usuarios.

## Requisitos

- Python 3.8 o posterior (no requiere instalar paquetes externos).
- Un navegador web actualizado.

## Iniciar el sitio

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py server.py
```

Si el comando `py` no está disponible, prueba:

```powershell
python server.py
```

Luego abre [http://127.0.0.1:8000/](http://127.0.0.1:8000/) en el navegador. Mantén abierta la ventana de PowerShell mientras uses el sitio. Para detener el servidor, presiona `Ctrl+C`.

Abre el sitio desde esa dirección para que los formularios puedan comunicarse con la API. No abras `index.html` directamente como archivo ni uses otro servidor estático, porque esos métodos no conectan con el servicio de registro.

## Registro e inicio de sesión

El formulario de [registro e inicio de sesión](paginas/registrarse1.html) envía los datos al servidor Python. La API valida los campos y almacena las cuentas en SQLite. Cada correo solo puede registrarse una vez. El inicio de sesión compara la contraseña con su hash almacenado.

El registro y el inicio de sesión requieren que el servidor esté activo. El servidor crea las tablas SQLite, valida las solicitudes y guarda las contraseñas con PBKDF2-HMAC-SHA256 y sal aleatoria. Después de registrarse, la página guarda el perfil de sesión en el navegador; en visitas posteriores se puede iniciar sesión con las credenciales guardadas en SQLite.

## Avisos de consultas por Gmail

Las consultas enviadas desde los detalles del producto se guardan en la bandeja del vendedor. Para enviar una copia por Gmail, configura una cuenta remitente con una contraseña de aplicación de Google (requiere Verificación en 2 pasos). No uses la contraseña normal de Gmail ni la publiques en el repositorio.

En PowerShell, define las variables en la misma ventana desde donde iniciarás el servidor:

```powershell
$env:GMAIL_SMTP_USER = "remitente@gmail.com"
$env:GMAIL_APP_PASSWORD = "contraseña-de-aplicación"
py server.py
```

`GMAIL_SMTP_USER` es la cuenta que envía el correo; el destinatario se toma del correo del vendedor asociado al producto. Si la configuración falta o Gmail rechaza el envío, la consulta permanece en la bandeja del sitio y la página lo indica. Google requiere Verificación en 2 pasos para crear contraseñas de aplicación. Consulta la [ayuda oficial de Google](https://support.google.com/accounts/answer/185833?hl=es).

## Base de datos

Al iniciar `server.py`, el sistema crea automáticamente `tablas/usuarios.db` si aún no existe. Ese archivo SQLite contiene la tabla `users` con estos campos:

| Campo | Descripción |
| --- | --- |
| `id` | Identificador único |
| `name` | Nombre del usuario |
| `email` | Correo único |
| `password_hash` | Hash PBKDF2-HMAC-SHA256 de la contraseña |
| `password_salt` | Sal aleatoria usada para el hash |
| `created_at` | Fecha de creación del registro |

Para consultar las cuentas, abre `tablas/usuarios.db` con un visor SQLite. El servidor no permite descargar el archivo de base de datos desde el sitio.

## Datos del navegador

Las cuentas se almacenan en SQLite. La sesión activa y otros datos de demostración, como el carrito y los productos publicados, todavía se guardan en `localStorage` del navegador; por ello esos datos no se comparten entre dispositivos ni navegadores.

Al quitar una foto, la portada del producto y las copias de esa foto en ambos carritos se actualizan. Al eliminar una publicación, también se quita del catálogo, de los destacados al actualizarse y de los carritos abiertos en otras pestañas. Los datos que ya estuvieran guardados en otro navegador o perfil deben borrarse desde ese mismo almacenamiento local.

## Archivos principales

Para empaquetar la tienda como app Android (APK), sigue [ANDROID_APK.md](ANDROID_APK.md).

- `server.py`: servidor web, API de autenticación y creación de la base SQLite.
- `paginas/registrarse1.html`: formularios de registro e inicio de sesión.
- `index.html`: página principal y productos destacados.
- `paginas/catalogo.html`: catálogo y detalle de productos.
- `paginas/carrito.html`: carrito y confirmación de compra.
- `paginas/vender.html`: publicación y gestión de productos.

> Esta configuración está pensada para ejecutar el proyecto localmente. Para publicar el sitio en Internet se necesitaría desplegar el servidor en un servicio seguro y configurar HTTPS, controles de sesión del lado del servidor y otras protecciones de producción.
