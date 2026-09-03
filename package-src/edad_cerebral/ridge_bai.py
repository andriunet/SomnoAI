"""El estimador del notebook 03_modelo.

    min (1/n)||Xw - y||² + (alpha/n)||w||² + lam·cov(BAI, y)²

El tercer término penaliza que el BAI (predicho − real) correlacione con la edad,
que es el sesgo de regresión a la media: sin él, el modelo señala a los jóvenes
como cerebros envejecidos y a los mayores como rejuvenecidos.

El alpha se divide por n para que la rejilla signifique lo mismo que en
sklearn.Ridge. Con lam=0 reproduce Ridge exactamente.

IMPORTANTE: esta clase debe vivir dentro del paquete y su ruta de importación no
puede cambiar. El Pipeline serializado guarda `edad_cerebral.ridge_bai.RidgeBAI`;
si el módulo se mueve o se renombra, todos los artefactos ya guardados dejan de
poder cargarse.
"""
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin


class RidgeBAI(BaseEstimator, RegressorMixin):
    def __init__(self, alpha=1.0, lam=0.0):
        self.alpha, self.lam = alpha, lam

    def fit(self, X, y):
        X, y = np.asarray(X, float), np.asarray(y, float)
        n, p = X.shape
        self.media_X_, self.media_y_ = X.mean(0), y.mean()
        Xc, c = X - self.media_X_, y - self.media_y_
        a = Xc.T @ c / n
        b = c @ c / n
        A = Xc.T @ Xc / n + (self.alpha / n) * np.eye(p) + self.lam * np.outer(a, a)
        self.coef_ = np.linalg.solve(A, (1 + self.lam * b) * a)
        self.intercept_ = self.media_y_ - self.media_X_ @ self.coef_
        return self

    def predict(self, X):
        return np.asarray(X, float) @ self.coef_ + self.intercept_
