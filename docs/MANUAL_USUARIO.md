## SomnoAI - Manual de Usuario del Tablero

Esta aplicación permite cargar una polisomnografía nocturna (EEG de sueño) para
estimar la **edad cerebral** del sujeto y el **Brain Age Index (BAI)**, un
criterio automático de priorización para un especialista en sueño. Consta de
tres secciones:

1. Registros (vista principal / historial)
2. Analizar un nuevo registro
3. Resultados del análisis

**Nota**: Es importante hacer este proceso de forma secuencial para garantizar
su funcionamiento: primero se inicia sesión, luego se carga y analiza un
registro, y por último se consultan sus resultados desde el historial.

**Nota**: Este manual asume que la API y el tablero ya están en ejecución
(`http://localhost:8000` y `http://localhost:8080`, o las URL del despliegue
del equipo). Ver `README.md` para las instrucciones de instalación y arranque.

---

### Paso 1. Acceder a la aplicación e ingresar credenciales para inicio de sesión

Abra la URL del tablero en el navegador. Se muestra la pantalla de inicio de
sesión con el nombre del proyecto: http://44.200.12.31:8050/ 

La aplicación tiene un único usuario administrador; no hay registro de cuentas
nuevas.

Ingrese el **usuario** y la **contraseña** en los campos correspondientes.
Ambos campos vienen prediligenciados con las credenciales del prototipo:
**superusuario / somnoai2026**.

![imagen de inicio de sesión](image.png)


Con la sesión iniciada, se puede pasar a analizar un nuevo registro o a
consultar el historial existente.

---

### Paso 2. Acceder a la pantalla Registros (vista principal)

La funcionalidad **Registros** muestra el historial de todos los análisis
realizados y un resumen general del comportamiento del BAI en la población
analizada con componentes tipo dashboard.

Desde la barra de navegación superior, seleccione la pestaña **Registros**
(es la vista con la que se abre la aplicación después de iniciar sesión).

En la parte superior se muestran cuatro indicadores: **registros
analizados**, **registros sobre el umbral** (|BAI| mayor a 10 años),
**divergencia mediana** del BAI y **fecha del último análisis**.

El panel **Distribución del BAI** muestra un punto por cada registro
analizado; la zona sombreada marca el umbral de priorización de ±10 años.

**Nota:** al pasar el mouse sobre un punto se muestra el detalle del registro
correspondiente.

La tabla **Historial de análisis** lista cada registro guardado con sujeto,
archivo, fecha, edad real, edad cerebral, BAI y estado (**En rango** o
**Priorizar**).

Use los botones **Todos** / **Sobre el umbral** para filtrar la tabla, o el
cuadro de búsqueda para filtrar por sujeto o nombre de archivo.

Haga clic en cualquier fila de la tabla (o en la flecha **→** al final de la
fila) para abrir el detalle de ese análisis en la vista **Resultados**.

Haga clic en el ícono de papelera al final de una fila para eliminar ese
análisis. Se abre un cuadro de confirmación con los datos del registro; haga
clic en **Borrar registro** para confirmar o en **Cancelar** para volver
atrás. Esta acción no se puede deshacer.

![pantalla registros](image-1.png)

---

## Paso 3. Analizar un nuevo registro

La funcionalidad **Analizar nuevo** permite subir una polisomnografía para
procesarla y obtener la estimación de edad cerebral.

Desde la barra de navegación superior, seleccione la pestaña **Analizar
nuevo**, o el botón **+ Analizar nuevo** en la vista Registros.

Para cargar el archivo de polisonmografia Arrastre el archivo al recuadro indicado o haga clic sobre él para buscarlo en
el equipo.

**Nota:** Los formatos permitidos son **.edf** (un solo canal PSG) o **.zip**
(con el par PSG + hipnograma), con un límite de **600 MB por archivo**.

![analizar nuevo](image-2.png)

Una vez seleccionado, el archivo aparece en una fila con su nombre y tamaño
mientras el navegador intenta detectar la edad y el sexo del sujeto desde el
encabezado del archivo.

**Nota:** si el archivo no es un `.edf` o `.zip` válido, o supera el límite de
tamaño, se muestra un mensaje de error y la carga no continúa.

Opcionalmente, se puede usar un registro del dataset. En el panel **O pruebe con un registro del dataset** hay tres noches
precargadas de Sleep-EDFx. Haga clic sobre cualquiera de ellas para analizarla
directamente, sin necesidad de subir un archivo propio.

El campo **Edad cronológica** se completa automáticamente cuando el
encabezado del archivo trae ese dato. Si el archivo no la trae, o si se quiere
fijar otra edad, se puede escribir manualmente; la edad escrita tiene
prioridad sobre la detectada.

**Nota:** la edad cronológica **no** es una característica del modelo; solo se
usa para calcular el BAI. Si el archivo no incluye hipnograma, la
estadificación del sueño se estima automáticamente.

![archivos cargados](image-3.png)

Cuando el archivo y la edad (detectada o ingresada) son válidos, se habilita
el botón **Analizar registro →**. Al hacer clic, se muestra el estado
**Analizando registro…** mientras la API procesa el archivo.

Al finalizar el procesamiento, la aplicación abre automáticamente la vista
**Resultados** con el detalle del análisis.

---

## Paso 4. Resultados del análisis

La vista **Resultados** presenta el detalle completo de un análisis: edad
cerebral, BAI, espectro frente a la norma de la edad, señal EEG navegable y
calidad del registro.

En la parte superior se muestra el nombre del archivo, la fecha y hora del
análisis, y el sexo y la edad utilizados.


El bloque principal muestra la **edad cerebral estimada** (con su intervalo de
predicción), la **edad cronológica** y el **Brain Age Index (BAI)**. Debajo se
muestra una escala visual y un mensaje que indica si el registro supera el
umbral de priorización de ±10 años.

El panel **Espectro frente a la norma de su edad** compara la potencia
espectral del EEG del sujeto (línea de color) contra el rango esperado para
sujetos de edad similar (banda gris), incluyendo el análisis del déficit de
husos de sueño.

El panel **Señal EEG a lo largo de la noche** permite navegar la señal cruda
del canal Fpz-Cz con el estadio de sueño anotado de fondo.

- Use los botones de ventana (**30 s**, **2 min**, **30 min**, **2 h**) para
  cambiar la escala de tiempo visible.
- Use las flechas **←** / **→** para moverse entre ventanas.
- Haga clic sobre la barra inferior para saltar directamente a otro momento de
  la noche.

**Nota:** el color de fondo indica el estadio de sueño (W, N1, N2, N3, REM);
la profundidad del azul sigue la profundidad del sueño.

El panel **Calidad del registro** resume qué contiene el archivo original
(duración, frecuencia de muestreo, canales) y qué parte de ese registro
alimentó efectivamente al modelo (ventana de sueño, épocas NREM utilizables,
vigilia recortada, entre otros).

![resultados parte 1](image-4.png)
![resultados parte 2](image-5.png)

Desde esta vista se puede volver al historial con **← Volver a registros**, o
analizar otro registro con el botón **Analizar otro registro**.

---

## Paso 5. Otras funciones

#### Cambiar entre tema claro y oscuro

El botón circular junto al usuario (o en la esquina de la tarjeta de inicio de
sesión) alterna entre tema claro y oscuro. La preferencia queda guardada en el
navegador.

![modo oscuro](image-6.png)

#### Cerrar sesión

El botón **Salir**, en la barra superior, cierra la sesión y regresa a la
pantalla de inicio de sesión.

![cerrar sesion](image-7.png)
