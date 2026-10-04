"""XGBoost model: attendance %, average test score, avg assignment lateness -> predicted final exam score.
Trained at startup on synthetic data; replace with real historical records for production."""
import numpy as np
from xgboost import XGBRegressor
_model = None
def _get():
    global _model
    if _model is None:
        r = np.random.default_rng(42); n = 2000
        att, avg, late = r.uniform(40, 100, n), r.uniform(20, 100, n), r.uniform(-2, 8, n)
        y = np.clip(0.6*avg + 0.3*att - 1.5*late + 5 + r.normal(0, 4, n), 0, 100)
        _model = XGBRegressor(n_estimators=150, max_depth=3, learning_rate=0.1)
        _model.fit(np.column_stack([att, avg, late]), y)
    return _model
def predict(att, avg, late):
    return round(float(_get().predict(np.array([[att, avg, late]]))[0]), 1)

def importance():
    return [round(float(x) * 100, 1) for x in _get().feature_importances_]
