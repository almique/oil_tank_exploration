import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
import joblib
from typing import List, Dict, Tuple, Optional
import logging
from datetime import datetime, timedelta
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    """Machine learning service for trend analysis and forecasting"""
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.model_dir = Path(settings.processed_data_dir) / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
    
    def prepare_features(self, measurements: List[Dict]) -> pd.DataFrame:
        """
        Prepare features for ML models from measurement data
        
        Args:
            measurements: List of measurement dictionaries
            
        Returns:
            DataFrame with engineered features
        """
        
        if not measurements:
            return pd.DataFrame()
        
        df = pd.DataFrame(measurements)
        df['created_at'] = pd.to_datetime(df['created_at'])
        df = df.sort_values('created_at')
        
        # Time-based features
        df['hour'] = df['created_at'].dt.hour
        df['day_of_week'] = df['created_at'].dt.dayofweek
        df['day_of_year'] = df['created_at'].dt.dayofyear
        df['month'] = df['created_at'].dt.month
        
        # Lag features
        for lag in [1, 3, 7, 14]:
            df[f'volume_lag_{lag}'] = df['volume_bbl'].shift(lag)
            df[f'fill_fraction_lag_{lag}'] = df['fill_fraction'].shift(lag)
        
        # Rolling statistics
        for window in [3, 7, 14, 30]:
            df[f'volume_rolling_mean_{window}'] = df['volume_bbl'].rolling(window).mean()
            df[f'volume_rolling_std_{window}'] = df['volume_bbl'].rolling(window).std()
            df[f'fill_rolling_mean_{window}'] = df['fill_fraction'].rolling(window).mean()
        
        # Change features
        df['volume_change_1d'] = df['volume_bbl'].diff(1)
        df['volume_change_7d'] = df['volume_bbl'].diff(7)
        df['volume_pct_change_1d'] = df['volume_bbl'].pct_change(1)
        df['volume_pct_change_7d'] = df['volume_bbl'].pct_change(7)
        
        # Confidence and quality features
        df['confidence_ma_7'] = df['confidence'].rolling(7).mean()
        df['measurement_count_7d'] = df.groupby(df['created_at'].dt.date).size().reindex(
            df['created_at'].dt.date, fill_value=0
        ).values
        
        # Weather proxy (seasonal patterns)
        df['sin_day_of_year'] = np.sin(2 * np.pi * df['day_of_year'] / 365.25)
        df['cos_day_of_year'] = np.cos(2 * np.pi * df['day_of_year'] / 365.25)
        
        return df
    
    def detect_anomalies(self, 
                        measurements: List[Dict], 
                        contamination: float = 0.1) -> List[bool]:
        """
        Detect anomalous measurements using Isolation Forest
        
        Args:
            measurements: List of measurement dictionaries
            contamination: Expected proportion of anomalies
            
        Returns:
            List of boolean flags indicating anomalies
        """
        
        df = self.prepare_features(measurements)
        
        if len(df) < 10:  # Need minimum data for anomaly detection
            return [False] * len(measurements)
        
        # Select features for anomaly detection
        feature_cols = [
            'volume_bbl', 'fill_fraction', 'confidence',
            'volume_change_1d', 'volume_pct_change_1d'
        ]
        
        # Remove rows with NaN values
        feature_df = df[feature_cols].dropna()
        
        if len(feature_df) < 5:
            return [False] * len(measurements)
        
        # Fit Isolation Forest
        iso_forest = IsolationForest(
            contamination=contamination,
            random_state=42,
            n_estimators=100
        )
        
        anomaly_labels = iso_forest.fit_predict(feature_df)
        
        # Map back to original indices
        anomalies = [False] * len(measurements)
        for i, idx in enumerate(feature_df.index):
            anomalies[idx] = anomaly_labels[i] == -1
        
        logger.info(f"Detected {sum(anomalies)} anomalies out of {len(measurements)} measurements")
        return anomalies
    
    def train_volume_forecaster(self, 
                              site_id: int,
                              measurements: List[Dict],
                              target_days: int = 7) -> Dict:
        """
        Train a volume forecasting model for a specific site
        
        Args:
            site_id: Site ID
            measurements: Historical measurement data
            target_days: Number of days ahead to forecast
            
        Returns:
            Training results and model performance metrics
        """
        
        df = self.prepare_features(measurements)
        
        if len(df) < 30:  # Need minimum data for training
            logger.warning(f"Insufficient data for site {site_id}: {len(df)} measurements")
            return {"error": "Insufficient data for training"}
        
        # Prepare target variable (future volume)
        df[f'target_volume_{target_days}d'] = df['volume_bbl'].shift(-target_days)
        
        # Select features
        feature_cols = [
            'volume_bbl', 'fill_fraction', 'confidence',
            'hour', 'day_of_week', 'month',
            'volume_lag_1', 'volume_lag_3', 'volume_lag_7',
            'volume_rolling_mean_7', 'volume_rolling_std_7',
            'volume_change_1d', 'volume_pct_change_1d',
            'sin_day_of_year', 'cos_day_of_year'
        ]
        
        # Remove rows with NaN values
        model_df = df[feature_cols + [f'target_volume_{target_days}d']].dropna()
        
        if len(model_df) < 20:
            logger.warning(f"Insufficient clean data for site {site_id}: {len(model_df)} rows")
            return {"error": "Insufficient clean data for training"}
        
        X = model_df[feature_cols]
        y = model_df[f'target_volume_{target_days}d']
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, shuffle=False
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train Random Forest model
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train_scaled, y_train)
        
        # Evaluate model
        y_pred_train = model.predict(X_train_scaled)
        y_pred_test = model.predict(X_test_scaled)
        
        train_mae = mean_absolute_error(y_train, y_pred_train)
        test_mae = mean_absolute_error(y_test, y_pred_test)
        train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
        test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
        
        # Feature importance
        feature_importance = dict(zip(feature_cols, model.feature_importances_))
        
        # Save model and scaler
        model_path = self.model_dir / f"volume_forecaster_site_{site_id}_{target_days}d.joblib"
        scaler_path = self.model_dir / f"scaler_site_{site_id}_{target_days}d.joblib"
        
        joblib.dump(model, model_path)
        joblib.dump(scaler, scaler_path)
        
        # Store in memory
        self.models[f"volume_{site_id}_{target_days}d"] = model
        self.scalers[f"volume_{site_id}_{target_days}d"] = scaler
        
        results = {
            "site_id": site_id,
            "target_days": target_days,
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "train_mae": train_mae,
            "test_mae": test_mae,
            "train_rmse": train_rmse,
            "test_rmse": test_rmse,
            "feature_importance": feature_importance,
            "model_path": str(model_path),
            "trained_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Trained volume forecaster for site {site_id}: MAE={test_mae:.2f}, RMSE={test_rmse:.2f}")
        return results
    
    def predict_volume(self, 
                      site_id: int,
                      recent_measurements: List[Dict],
                      target_days: int = 7) -> Optional[Dict]:
        """
        Predict future volume for a site
        
        Args:
            site_id: Site ID
            recent_measurements: Recent measurement data
            target_days: Number of days ahead to predict
            
        Returns:
            Prediction results or None if model not available
        """
        
        model_key = f"volume_{site_id}_{target_days}d"
        
        # Load model if not in memory
        if model_key not in self.models:
            model_path = self.model_dir / f"volume_forecaster_site_{site_id}_{target_days}d.joblib"
            scaler_path = self.model_dir / f"scaler_site_{site_id}_{target_days}d.joblib"
            
            if not model_path.exists() or not scaler_path.exists():
                logger.warning(f"No trained model found for site {site_id}, {target_days}d forecast")
                return None
            
            self.models[model_key] = joblib.load(model_path)
            self.scalers[model_key] = joblib.load(scaler_path)
        
        # Prepare features
        df = self.prepare_features(recent_measurements)
        
        if len(df) == 0:
            return None
        
        # Get latest features
        feature_cols = [
            'volume_bbl', 'fill_fraction', 'confidence',
            'hour', 'day_of_week', 'month',
            'volume_lag_1', 'volume_lag_3', 'volume_lag_7',
            'volume_rolling_mean_7', 'volume_rolling_std_7',
            'volume_change_1d', 'volume_pct_change_1d',
            'sin_day_of_year', 'cos_day_of_year'
        ]
        
        latest_features = df[feature_cols].iloc[-1:].dropna(axis=1)
        
        # Check if we have enough features
        if len(latest_features.columns) < len(feature_cols) * 0.7:  # Need at least 70% of features
            logger.warning(f"Insufficient features for prediction: {len(latest_features.columns)}/{len(feature_cols)}")
            return None
        
        # Align features with training data
        model = self.models[model_key]
        scaler = self.scalers[model_key]
        
        # Fill missing features with median values (simple imputation)
        for col in feature_cols:
            if col not in latest_features.columns:
                latest_features[col] = df[col].median() if col in df.columns else 0
        
        latest_features = latest_features[feature_cols]
        
        # Scale and predict
        features_scaled = scaler.transform(latest_features)
        prediction = model.predict(features_scaled)[0]
        
        # Calculate prediction confidence (using model's prediction intervals)
        # For Random Forest, we can use the std of tree predictions
        tree_predictions = np.array([tree.predict(features_scaled)[0] for tree in model.estimators_])
        prediction_std = np.std(tree_predictions)
        confidence_interval = (prediction - 1.96 * prediction_std, prediction + 1.96 * prediction_std)
        
        return {
            "site_id": site_id,
            "target_days": target_days,
            "predicted_volume_bbl": prediction,
            "confidence_interval": confidence_interval,
            "prediction_std": prediction_std,
            "current_volume_bbl": df['volume_bbl'].iloc[-1] if 'volume_bbl' in df.columns else None,
            "predicted_change_bbl": prediction - (df['volume_bbl'].iloc[-1] if 'volume_bbl' in df.columns else 0),
            "predicted_at": datetime.utcnow().isoformat()
        }
    
    def analyze_trends(self, measurements: List[Dict]) -> Dict:
        """
        Analyze trends in measurement data
        
        Args:
            measurements: List of measurement dictionaries
            
        Returns:
            Trend analysis results
        """
        
        df = self.prepare_features(measurements)
        
        if len(df) < 7:
            return {"error": "Insufficient data for trend analysis"}
        
        # Calculate various trend metrics
        recent_7d = df.tail(7)
        recent_30d = df.tail(30) if len(df) >= 30 else df
        
        # Volume trends
        volume_trend_7d = self._calculate_trend(recent_7d['volume_bbl'].values)
        volume_trend_30d = self._calculate_trend(recent_30d['volume_bbl'].values)
        
        # Fill fraction trends
        fill_trend_7d = self._calculate_trend(recent_7d['fill_fraction'].values)
        fill_trend_30d = self._calculate_trend(recent_30d['fill_fraction'].values)
        
        # Volatility (coefficient of variation)
        volume_volatility_7d = recent_7d['volume_bbl'].std() / recent_7d['volume_bbl'].mean() if recent_7d['volume_bbl'].mean() > 0 else 0
        volume_volatility_30d = recent_30d['volume_bbl'].std() / recent_30d['volume_bbl'].mean() if recent_30d['volume_bbl'].mean() > 0 else 0
        
        # Seasonal patterns (if enough data)
        seasonal_strength = 0
        if len(df) >= 365:
            seasonal_strength = self._calculate_seasonal_strength(df['volume_bbl'].values)
        
        return {
            "volume_trend_7d": volume_trend_7d,
            "volume_trend_30d": volume_trend_30d,
            "fill_trend_7d": fill_trend_7d,
            "fill_trend_30d": fill_trend_30d,
            "volume_volatility_7d": volume_volatility_7d,
            "volume_volatility_30d": volume_volatility_30d,
            "seasonal_strength": seasonal_strength,
            "data_points": len(df),
            "analysis_date": datetime.utcnow().isoformat()
        }
    
    def _calculate_trend(self, values: np.ndarray) -> Dict:
        """Calculate trend statistics for a time series"""
        
        if len(values) < 2:
            return {"direction": "stable", "slope": 0, "r_squared": 0}
        
        # Remove NaN values
        clean_values = values[~np.isnan(values)]
        
        if len(clean_values) < 2:
            return {"direction": "stable", "slope": 0, "r_squared": 0}
        
        # Linear regression
        x = np.arange(len(clean_values))
        coeffs = np.polyfit(x, clean_values, 1)
        slope = coeffs[0]
        
        # R-squared
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((clean_values - y_pred) ** 2)
        ss_tot = np.sum((clean_values - np.mean(clean_values)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Determine direction
        if abs(slope) < np.std(clean_values) * 0.1:  # Less than 10% of std dev
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        
        return {
            "direction": direction,
            "slope": slope,
            "r_squared": r_squared,
            "mean_value": np.mean(clean_values),
            "std_value": np.std(clean_values)
        }
    
    def _calculate_seasonal_strength(self, values: np.ndarray) -> float:
        """Calculate seasonal strength using autocorrelation"""
        
        # Simple seasonal strength using 7-day and 30-day autocorrelation
        try:
            from scipy.stats import pearsonr
            
            if len(values) < 60:
                return 0
            
            # 7-day seasonality
            corr_7d, _ = pearsonr(values[:-7], values[7:])
            
            # 30-day seasonality
            if len(values) >= 60:
                corr_30d, _ = pearsonr(values[:-30], values[30:])
            else:
                corr_30d = 0
            
            return max(abs(corr_7d), abs(corr_30d))
            
        except Exception:
            return 0

class MLService:
    """Main ML service for oil tank monitoring"""
    
    def __init__(self):
        self.trend_analyzer = TrendAnalyzer()
    
    def process_site_ml_analysis(self, 
                               site_id: int,
                               measurements: List[Dict]) -> Dict:
        """
        Run complete ML analysis for a site
        
        Args:
            site_id: Site ID
            measurements: Historical measurements
            
        Returns:
            Complete ML analysis results
        """
        
        results = {
            "site_id": site_id,
            "processed_at": datetime.utcnow().isoformat(),
            "measurement_count": len(measurements)
        }
        
        try:
            # Anomaly detection
            anomalies = self.trend_analyzer.detect_anomalies(measurements)
            results["anomalies"] = {
                "detected_count": sum(anomalies),
                "anomaly_rate": sum(anomalies) / len(measurements) if measurements else 0,
                "anomaly_indices": [i for i, is_anomaly in enumerate(anomalies) if is_anomaly]
            }
            
            # Trend analysis
            trend_analysis = self.trend_analyzer.analyze_trends(measurements)
            results["trends"] = trend_analysis
            
            # Volume forecasting (7-day)
            if len(measurements) >= 30:
                forecast_7d = self.trend_analyzer.predict_volume(site_id, measurements, 7)
                if forecast_7d:
                    results["forecast_7d"] = forecast_7d
                
                # Train/retrain model if needed
                training_results = self.trend_analyzer.train_volume_forecaster(site_id, measurements, 7)
                results["model_training"] = training_results
            
            logger.info(f"Completed ML analysis for site {site_id}")
            
        except Exception as e:
            logger.error(f"Error in ML analysis for site {site_id}: {e}")
            results["error"] = str(e)
        
        return results
