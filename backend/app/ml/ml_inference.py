import joblib
import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# VOLTEDGE ML INFERENCE MODULE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ENERGY_MODEL_PATH = BASE_DIR / "voltedge_energy_model_full.pkl"
ANOMALY_MODEL_PATH = BASE_DIR / "voltedge_anomaly_models.pkl"


# ============================================================
# LOAD TRAINED MODELS
# ============================================================

energy_package = joblib.load(ENERGY_MODEL_PATH)
anomaly_models = joblib.load(ANOMALY_MODEL_PATH)

energy_model = energy_package["model"]
energy_features = energy_package["features"]
numeric_features = energy_package["numeric_features"]
asset_columns = energy_package["asset_columns"]


# ============================================================
# FEATURE PREPARATION
# ============================================================

def prepare_features(data):
    """
    Prepare raw energy data for VoltEdge ML inference.

    Creates:
        - time features
        - lag features
        - energy change features
        - cyclical time features
        - asset one-hot features
    """

    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)

    df = data.copy()

    # --------------------------------------------------------
    # Validate required columns
    # --------------------------------------------------------

    required_columns = [
        "AssetId",
        "window_start_utc",
        "Energy_kWh_15m"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required input columns: {missing_columns}"
        )

    # --------------------------------------------------------
    # Convert timestamp
    # --------------------------------------------------------

    df["window_start_utc"] = pd.to_datetime(
        df["window_start_utc"],
        errors="coerce"
    )

    if df["window_start_utc"].isna().any():
        raise ValueError(
            "Some window_start_utc values could not be converted "
            "to datetime."
        )

    # --------------------------------------------------------
    # Sort by asset and timestamp
    # --------------------------------------------------------

    df = df.sort_values(
        ["AssetId", "window_start_utc"]
    ).copy()

    # --------------------------------------------------------
    # Time features
    # --------------------------------------------------------

    df["hour"] = df["window_start_utc"].dt.hour

    df["minute"] = df["window_start_utc"].dt.minute

    df["day_of_week"] = (
        df["window_start_utc"].dt.dayofweek
    )

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    # --------------------------------------------------------
    # Cyclical time features
    # --------------------------------------------------------

    df["hour_sin"] = np.sin(
        2 * np.pi * df["hour"] / 24
    )

    df["hour_cos"] = np.cos(
        2 * np.pi * df["hour"] / 24
    )

    df["day_sin"] = np.sin(
        2 * np.pi * df["day_of_week"] / 7
    )

    df["day_cos"] = np.cos(
        2 * np.pi * df["day_of_week"] / 7
    )

    # --------------------------------------------------------
    # Lag features
    # --------------------------------------------------------

    grouped_energy = (
        df.groupby("AssetId")["Energy_kWh_15m"]
    )

    df["lag_1"] = grouped_energy.shift(1)

    df["lag_2"] = grouped_energy.shift(2)

    df["lag_4"] = grouped_energy.shift(4)

    df["lag_8"] = grouped_energy.shift(8)

    df["lag_96"] = grouped_energy.shift(96)

    # --------------------------------------------------------
    # Energy change features
    # --------------------------------------------------------

    previous_energy = (
        df.groupby("AssetId")["Energy_kWh_15m"]
        .shift(1)
    )

    df["energy_change"] = (
        df["Energy_kWh_15m"]
        - previous_energy
    )

    df["energy_change_pct"] = np.where(
        previous_energy != 0,
        (
            df["energy_change"]
            / previous_energy
        ) * 100,
        0
    )

    # --------------------------------------------------------
    # Daily change
    #
    # 96 x 15 minutes = 24 hours
    # --------------------------------------------------------

    daily_previous_energy = (
        df.groupby("AssetId")["Energy_kWh_15m"]
        .shift(96)
    )

    df["daily_change"] = (
        df["Energy_kWh_15m"]
        - daily_previous_energy
    )

    df["daily_change_pct"] = np.where(
        daily_previous_energy != 0,
        (
            df["daily_change"]
            / daily_previous_energy
        ) * 100,
        0
    )

    # --------------------------------------------------------
    # Asset one-hot encoding
    #
    # The trained energy model expects columns such as:
    #
    # asset_ahu_a
    # asset_ahu_b
    # asset_comp_a
    # ...
    # --------------------------------------------------------

    asset_dummies = pd.get_dummies(
        df["AssetId"],
        prefix="asset"
    )

    # Make sure the exact asset columns used during
    # training exist.

    asset_dummies = asset_dummies.reindex(
        columns=asset_columns,
        fill_value=0
    )

    # Remove any existing copies.

    df = df.drop(
        columns=asset_columns,
        errors="ignore"
    )

    # Add the correctly ordered asset columns.

    df = pd.concat(
        [
            df,
            asset_dummies
        ],
        axis=1
    )

    # --------------------------------------------------------
    # Make sure all model features exist
    # --------------------------------------------------------

    all_required_features = set(
        energy_features
    )

    missing_features = [
        feature
        for feature in all_required_features
        if feature not in df.columns
    ]

    if missing_features:
        raise ValueError(
            "Feature preparation failed. Missing features: "
            f"{missing_features}"
        )

    return df


# ============================================================
# ENERGY PREDICTION
# ============================================================

def predict_energy(data):
    """
    Predict expected energy consumption.

    The trained energy model uses:
        - lag features
        - time features
        - asset one-hot features
    """

    df = prepare_features(data)

    # --------------------------------------------------------
    # Select features in EXACT training order
    # --------------------------------------------------------

    X = df[energy_features].copy()

    # --------------------------------------------------------
    # Convert values to numeric
    # --------------------------------------------------------

    for column in X.columns:
        X[column] = pd.to_numeric(
            X[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # Check missing values
    # --------------------------------------------------------

    missing_count = X.isna().sum()

    rows_with_missing = missing_count[
        missing_count > 0
    ]

    if len(rows_with_missing) > 0:

        print(
            "\nWarning: some rows do not have enough "
            "historical data for energy prediction."
        )

        print(
            "Missing values by feature:"
        )

        print(rows_with_missing)

    # --------------------------------------------------------
    # Predict only valid rows
    # --------------------------------------------------------

    valid_rows = X.notna().all(axis=1)

    df["expected_energy_kwh"] = np.nan

    if valid_rows.any():

        predictions = energy_model.predict(
            X.loc[valid_rows]
        )

        df.loc[
            valid_rows,
            "expected_energy_kwh"
        ] = predictions

    return df


# ============================================================
# ANOMALY DETECTION
# ============================================================

def detect_anomalies(data):
    """
    Detect anomalies using the asset-specific
    Isolation Forest models.
    """

    df = prepare_features(data)

    results = []

    # --------------------------------------------------------
    # Process each asset separately
    # --------------------------------------------------------

    for asset_id, asset_df in df.groupby(
        "AssetId",
        sort=False
    ):

        asset_df = asset_df.copy()

        # ----------------------------------------------------
        # Check if trained model exists
        # ----------------------------------------------------

        if asset_id not in anomaly_models:

            asset_df["anomaly_flag"] = np.nan

            asset_df["anomaly_score"] = np.nan

            asset_df["severity"] = (
                "MODEL_NOT_AVAILABLE"
            )

            results.append(asset_df)

            continue

        # ----------------------------------------------------
        # Get saved model package
        # ----------------------------------------------------

        package = anomaly_models[asset_id]

        model = package["model"]

        scaler = package["scaler"]

        features = package["features"]

        # ----------------------------------------------------
        # Check required anomaly features
        # ----------------------------------------------------

        missing_features = [
            feature
            for feature in features
            if feature not in asset_df.columns
        ]

        if missing_features:

            asset_df["anomaly_flag"] = np.nan

            asset_df["anomaly_score"] = np.nan

            asset_df["severity"] = (
                "INSUFFICIENT_FEATURES"
            )

            results.append(asset_df)

            continue

        # ----------------------------------------------------
        # Prepare anomaly features
        # ----------------------------------------------------

        X = asset_df[features].copy()

        for column in X.columns:
            X[column] = pd.to_numeric(
                X[column],
                errors="coerce"
            )

        # ----------------------------------------------------
        # Initialize outputs
        # ----------------------------------------------------

        asset_df["anomaly_flag"] = np.nan

        asset_df["anomaly_score"] = np.nan

        asset_df["severity"] = "NORMAL"

        # ----------------------------------------------------
        # Only process rows with complete history
        # ----------------------------------------------------

        valid_rows = X.notna().all(axis=1)

        if valid_rows.any():

            X_valid = X.loc[valid_rows]

            # Scale using the SAME scaler used during training.

            X_scaled = scaler.transform(
                X_valid
            )

            # Isolation Forest:
            #
            #  1  = normal
            # -1  = anomaly

            predictions = model.predict(
                X_scaled
            )

            scores = model.decision_function(
                X_scaled
            )

            anomaly_flags = (
                predictions == -1
            ).astype(int)

            asset_df.loc[
                valid_rows,
                "anomaly_flag"
            ] = anomaly_flags

            asset_df.loc[
                valid_rows,
                "anomaly_score"
            ] = scores

            # ------------------------------------------------
            # Severity
            # ------------------------------------------------

            asset_df.loc[
                valid_rows,
                "severity"
            ] = "NORMAL"

            # Anomaly → MEDIUM

            anomaly_mask = (
                asset_df["anomaly_flag"] == 1
            )

            asset_df.loc[
                anomaly_mask,
                "severity"
            ] = "MEDIUM"

            # Strong anomaly → HIGH

            high_mask = (
                (asset_df["anomaly_flag"] == 1)
                &
                (asset_df["anomaly_score"] < -0.05)
            )

            asset_df.loc[
                high_mask,
                "severity"
            ] = "HIGH"

            # Very strong anomaly → CRITICAL

            critical_mask = (
                (asset_df["anomaly_flag"] == 1)
                &
                (asset_df["anomaly_score"] < -0.15)
            )

            asset_df.loc[
                critical_mask,
                "severity"
            ] = "CRITICAL"

        results.append(asset_df)

    # --------------------------------------------------------
    # Combine all assets
    # --------------------------------------------------------

    if not results:
        return df

    return pd.concat(
        results,
        ignore_index=True
    )


# ============================================================
# ENERGY IMPACT CALCULATION
# ============================================================

def calculate_energy_impact(
    data,
    tariff_rupees_per_kwh=8.0
):
    """
    Calculate potential excess energy and
    estimated cost impact.

    IMPORTANT:
    This is potential/model-estimated impact,
    not confirmed real-world savings.
    """

    result = data.copy()

    # --------------------------------------------------------
    # Required columns
    # --------------------------------------------------------

    required_columns = [
        "Energy_kWh_15m",
        "expected_energy_kwh",
        "anomaly_flag"
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in result.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing columns for energy impact: "
            f"{missing_columns}"
        )

    # --------------------------------------------------------
    # Actual minus expected
    # --------------------------------------------------------

    result["excess_energy_kwh"] = (
        result["Energy_kWh_15m"]
        - result["expected_energy_kwh"]
    )

    # --------------------------------------------------------
    # Potential waste
    #
    # Only count:
    # 1. anomaly
    # 2. actual > expected
    # --------------------------------------------------------

    result["potential_waste_kwh"] = np.where(
        (
            (result["anomaly_flag"] == 1)
            &
            (result["excess_energy_kwh"] > 0)
        ),
        result["excess_energy_kwh"],
        0
    )

    # --------------------------------------------------------
    # Unusually LOW consumption
    # --------------------------------------------------------

    result[
        "unusual_low_consumption_kwh"
    ] = np.where(
        (
            (result["anomaly_flag"] == 1)
            &
            (result["excess_energy_kwh"] < 0)
        ),
        abs(result["excess_energy_kwh"]),
        0
    )

    # --------------------------------------------------------
    # Potential cost impact
    # --------------------------------------------------------

    result["potential_cost_impact"] = (
        result["potential_waste_kwh"]
        * tariff_rupees_per_kwh
    )

    return result


# ============================================================
# COMPLETE ML PIPELINE
# ============================================================

def run_ml_pipeline(
    data,
    tariff_rupees_per_kwh=8.0
):
    """
    Run the complete VoltEdge ML pipeline.

    Returns:

        actual energy
        expected energy
        anomaly flag
        anomaly score
        severity
        excess energy
        potential waste
        potential cost impact
    """

    # --------------------------------------------------------
    # STEP 1: ENERGY PREDICTION
    # --------------------------------------------------------

    energy_result = predict_energy(
        data
    )

    # --------------------------------------------------------
    # STEP 2: ANOMALY DETECTION
    # --------------------------------------------------------

    anomaly_result = detect_anomalies(
        data
    )

    # --------------------------------------------------------
    # STEP 3: Add anomaly outputs
    #
    # Both functions preserve the same sorted row order.
    # Reset index to ensure alignment.
    # --------------------------------------------------------

    energy_result = energy_result.reset_index(
        drop=True
    )

    anomaly_result = anomaly_result.reset_index(
        drop=True
    )

    energy_result[
        "anomaly_flag"
    ] = anomaly_result[
        "anomaly_flag"
    ]

    energy_result[
        "anomaly_score"
    ] = anomaly_result[
        "anomaly_score"
    ]

    energy_result[
        "severity"
    ] = anomaly_result[
        "severity"
    ]

    # --------------------------------------------------------
    # STEP 4: ENERGY IMPACT
    # --------------------------------------------------------

    final_result = calculate_energy_impact(
        energy_result,
        tariff_rupees_per_kwh=tariff_rupees_per_kwh
    )

    return final_result


# ============================================================
# SINGLE LATEST RESULT
# ============================================================

def predict_single(
    data,
    tariff_rupees_per_kwh=8.0
):
    """
    Return the latest ML prediction as a dictionary.

    Input must contain enough historical observations
    for the required lag features.
    """

    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)

    result = run_ml_pipeline(
        data,
        tariff_rupees_per_kwh=tariff_rupees_per_kwh
    )

    # Latest timestamp

    result = result.sort_values(
        "window_start_utc"
    )

    latest = result.iloc[-1].copy()

    # Convert NumPy values into normal Python values
    # so that backend APIs can serialize them easily.

    output = {}

    for key, value in latest.items():

        if pd.isna(value):
            output[key] = None

        elif isinstance(
            value,
            (np.integer,)
        ):
            output[key] = int(value)

        elif isinstance(
            value,
            (np.floating,)
        ):
            output[key] = float(value)

        else:
            output[key] = value

    return output


# ============================================================
# SUMMARY FUNCTION
# ============================================================

def summarize_results(result):
    """
    Generate a compact summary of ML results.
    """

    summary = {
        "total_observations": int(
            len(result)
        ),

        "total_anomalies": int(
            result["anomaly_flag"]
            .fillna(0)
            .sum()
        ),

        "potential_waste_kwh": float(
            result["potential_waste_kwh"]
            .fillna(0)
            .sum()
        ),

        "potential_cost_impact_rupees": float(
            result["potential_cost_impact"]
            .fillna(0)
            .sum()
        ),

        "critical_anomalies": int(
            (
                result["severity"]
                == "CRITICAL"
            ).sum()
        ),

        "high_anomalies": int(
            (
                result["severity"]
                == "HIGH"
            ).sum()
        ),

        "medium_anomalies": int(
            (
                result["severity"]
                == "MEDIUM"
            ).sum()
        )
    }

    return summary


# ============================================================
# MODULE TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("VoltEdge ML Inference Module")
    print("=" * 70)

    print()
    print(
        "Energy model features:"
    )

    print(
        energy_features
    )

    print()
    print(
        "Available anomaly models:",
        len(anomaly_models)
    )

    print()
    print(
        "Assets:"
    )

    print(
        list(anomaly_models.keys())
    )

    print()
    print(
        "ML module loaded successfully."
    )

    print("=" * 70)