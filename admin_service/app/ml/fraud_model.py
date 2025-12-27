# admin_service/app/ml/fraud_model.py
import os
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime
from .feature_engineering import compute_features_for_campaign, compute_rule_hits

MODEL_DIR = os.environ.get("FRAUD_MODEL_DIR", "admin_service/app/ml/models")
MODEL_FILENAME = os.environ.get("FRAUD_MODEL_FILE", "isoforest_v1.joblib")
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)

# ensure model dir exists when saving
os.makedirs(MODEL_DIR, exist_ok=True)

class FraudDetector:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self.model_version = None
        self.load()

    def load(self):
        try:
            self.model = joblib.load(self.model_path)
            self.model_version = getattr(self.model, "model_version", "isof_v1")
            # sklearn IsolationForest is expected
        except Exception:
            self.model = None
            self.model_version = None

    def save(self, model, version=None):
        # attach metadata
        try:
            setattr(model, "model_version", version or f"isof_{datetime.utcnow().strftime('%Y%m%d%H%M')}")
            joblib.dump(model, self.model_path)
            self.model = model
            self.model_version = getattr(model, "model_version", None)
            return True
        except Exception as e:
            print("Failed to save model:", e)
            return False

    def train_from_matrix(self, X, n_estimators=100, random_state=42):
        """
        X: numpy array shape (n_samples, n_features)
        """
        model = IsolationForest(n_estimators=n_estimators, contamination='auto', random_state=random_state)
        model.fit(X)
        version = f"isof_{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        self.save(model, version)
        return model

    def _vector_from_features(self, features: dict, keys_sorted=None):
        # deterministic ordering
        if keys_sorted is None:
            keys_sorted = sorted(features.keys())
        return np.array([features[k] for k in keys_sorted], dtype=float)

    def score_campaign(self, campaign: dict, user: dict, model_weight=0.6):
        """
        Returns dict:
        {
          score: 0.0-1.0 (higher=more risky),
          rule_hits: [...],
          model_score: 0.0-1.0,
          model_version: str,
          scored_at: iso
        }
        """
        rule_hits = compute_rule_hits(campaign, user)
        # rule_score: if any critical rule -> 1.0, else scaled by number of hits
        rule_score = 0.0
        if any(r.get("severity") == "critical" for r in rule_hits):
            rule_score = 1.0
        elif len(rule_hits) > 0:
            # warning -> 0.5 each up to 0.8
            rule_score = min(0.8, 0.2 * len(rule_hits))

        features = compute_features_for_campaign(campaign, user)
        keys_sorted = sorted(features.keys())
        vec = self._vector_from_features(features, keys_sorted).reshape(1, -1)

        model_score = 0.0
        if self.model is not None:
            try:
                # IsolationForest.decision_function: higher -> less anomalous
                raw = self.model.decision_function(vec)[0]
                # convert: more anomalous => higher number in 0..1
                # flip sign and pass through sigmoid-like mapping
                anom = -float(raw)
                model_score = 1.0 / (1.0 + np.exp(- (anom)))  # sigmoid centered at 0
                model_version = getattr(self.model, "model_version", None)
            except Exception:
                model_score = 0.0
                model_version = self.model_version
        else:
            model_version = None

        final_score = max(rule_score, model_weight * model_score)

        return {
            "score": float(round(final_score, 6)),
            "rule_hits": rule_hits,
            "model_score": float(round(model_score, 6)),
            "model_version": model_version,
            "scored_at": datetime.utcnow().isoformat() + "Z",
            "features_used": features
        }
