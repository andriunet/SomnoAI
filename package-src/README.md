# edad_cerebral

Estimación de la **edad cerebral** a partir del EEG de una polisomnografía nocturna.
Empaqueta el modelo del **experimento C** descrito en
`Microproyectos/Microproyecto/Experimentos/Sebastian/README.md`.

```python
from edad_cerebral.predict import predecir_desde_edf

r = predecir_desde_edf("SC4001E0-PSG.edf", "SC4001EC-Hypnogram.edf")
r["edad_cerebral"]    # 41.7
```

## El modelo

Ridge con corrección del sesgo del BAI (`RidgeBAI`), `alpha = 3.16`, `lambda = 0.01`,
sobre **32 columnas**: las 12 características espectrales de cada uno de los dos canales
de EEG (`EEG Fpz-Cz` y `EEG Pz-Oz`) más 8 de arquitectura del sueño.

| MAE (años) | |
|---|---:|
| train | 7,48 |
| **validación cruzada** | **10,43** |
| test | 9,15 |
| predecir siempre la media | 19,10 |

**La cifra defendible es 10,43.** El 9,15 son 16 sujetos consultados muchas veces a lo
largo del proyecto, así que está sesgado a la baja. El 10,43 también lo está, aunque
menos: es el mínimo sobre una rejilla de 91 evaluaciones ruidosas, y el mínimo de muchas
estimaciones ruidosas es optimista por construcción. Es una cota inferior del error real,
no una estimación insesgada.

## Estructura

```
edad_cerebral/
  config.yml            bandas, canales, alpha/lambda, columnas, métricas esperadas
  config/core.py        lo valida con Pydantic → objeto `config`
  processing/
    edf.py              lectura del EDF, recorte de la noche, validaciones del archivo
    features.py         doce_numeros, arquitectura  (del notebook 02)
    data_manager.py     guardar y cargar el artefacto
    validation.py       validación de las 32 características
  ridge_bai.py          el estimador                (del notebook 03)
  pipeline.py           imputar → escalar → RidgeBAI
  train_pipeline.py     reconstruye el artefacto desde datasets/
  predict.py            make_prediction / predecir_desde_edf
  datasets/             las dos tablas de características y la partición
  trained/              el artefacto .pkl
```

## Reentrenar

```bash
tox run -e train
```

Lee `datasets/`, ajusta sobre los **62 sujetos de desarrollo** y **aborta si no reproduce
7,48 / 10,43 / 9,15**. No se entrena con los 78: el test se deja intacto para que las
cifras del reporte sigan siendo las del modelo desplegado.

## Nota sobre las versiones

`requirements/requirements.txt` fija las versiones **del entorno de servicio**, no las del
portátil donde se explora. Las tablas de `datasets/` se calcularon con una versión concreta
de `scipy`, y el `StandardScaler` del modelo está ajustado sobre esos números: extraer en
producción con otra versión movería las características **sin lanzar ningún error** y la
predicción saldría corrida.

## Límites

- El modelo se entrenó con el **promedio de las dos noches** de cada sujeto. Al predecir
  sobre una noche suelta el error es algo mayor que 10,43.
- El entrenamiento usó **hipnogramas anotados por expertos**. Con etapas estimadas
  automáticamente las etiquetas no son las que vio el modelo.
- Requiere **los dos canales de EEG**. Un archivo sin `EEG Pz-Oz` se rechaza.
