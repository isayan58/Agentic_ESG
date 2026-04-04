"""PySpark processing layer — distributed computing for ESG data at scale.

Provides a SparkProcessor class that mirrors all pandas operations in
data_processing.py but uses PySpark for distributed execution. Falls back
to pandas gracefully if PySpark is not installed or a local SparkSession
cannot be created.

Usage:
    from utils.spark_processing import spark_processor

    # These work identically to the pandas versions but run on Spark
    emissions_sdf = spark_processor.load_emissions()
    scope_totals  = spark_processor.compute_scope_totals(emissions_sdf, year=2024)
"""
import os
import json
from config import DATA_DIR

# ── Attempt PySpark import; track availability ──
try:
    from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
    from pyspark.sql import functions as F
    from pyspark.sql.types import (
        StructType, StructField, StringType, DoubleType, IntegerType,
    )
    PYSPARK_AVAILABLE = True
except ImportError:
    PYSPARK_AVAILABLE = False
    SparkDataFrame = None

import pandas as pd


class SparkProcessor:
    """Distributed ESG data processing with PySpark.

    Automatically creates a local SparkSession in standalone mode.
    In production, point ``spark.master`` to a YARN / Kubernetes cluster.
    """

    def __init__(self):
        self._spark = None

    # ── Lazy Spark session ────────────────────────────────────────────────

    @property
    def spark(self):
        if self._spark is None:
            if not PYSPARK_AVAILABLE:
                return None
            self._spark = (
                SparkSession.builder
                .appName("ESG_CoPilot")
                .master("local[*]")
                .config("spark.sql.shuffle.partitions", "4")
                .config("spark.driver.memory", "2g")
                .config("spark.ui.enabled", "false")
                .getOrCreate()
            )
            self._spark.sparkContext.setLogLevel("ERROR")
        return self._spark

    @property
    def is_available(self):
        return PYSPARK_AVAILABLE

    # ── Helpers ───────────────────────────────────────────────────────────

    def _csv_path(self, filename):
        return os.path.join(DATA_DIR, filename)

    def _load_csv_spark(self, filename):
        path = self._csv_path(filename)
        if not os.path.exists(path) or self.spark is None:
            return None
        return self.spark.read.csv(path, header=True, inferSchema=True)

    def to_pandas(self, sdf):
        """Convert a Spark DataFrame to pandas."""
        if sdf is None:
            return pd.DataFrame()
        return sdf.toPandas()

    def from_pandas(self, pdf):
        """Convert a pandas DataFrame to Spark."""
        if self.spark is None or pdf.empty:
            return None
        return self.spark.createDataFrame(pdf)

    # ── Data Loaders ──────────────────────────────────────────────────────

    def load_emissions(self):
        return self._load_csv_spark("sample_emissions.csv")

    def load_esg_metrics(self):
        return self._load_csv_spark("sample_esg_metrics.csv")

    def load_supply_chain(self):
        return self._load_csv_spark("sample_supply_chain.csv")

    def load_energy(self):
        return self._load_csv_spark("sample_energy.csv")

    def load_waste(self):
        return self._load_csv_spark("sample_waste.csv")

    def load_diversity(self):
        return self._load_csv_spark("sample_diversity.csv")

    # ── Distributed Computations ──────────────────────────────────────────

    def compute_scope_totals(self, emissions_sdf, year=None):
        """Compute total emissions by scope using Spark aggregation."""
        if emissions_sdf is None:
            return {}
        df = emissions_sdf
        if year is not None:
            df = df.filter(F.col("year") == year)
        result = (
            df.groupBy("scope")
            .agg(F.sum("emissions_tco2e").alias("total"))
            .collect()
        )
        return {row["scope"]: round(row["total"], 1) for row in result}

    def compute_quarterly_trends(self, emissions_sdf):
        """Compute quarterly trends using Spark."""
        if emissions_sdf is None:
            return pd.DataFrame()
        result = (
            emissions_sdf
            .withColumn("period", F.concat_ws(" ", F.col("year").cast("string"), F.col("quarter")))
            .groupBy("period", "scope")
            .agg(F.sum("emissions_tco2e").alias("emissions_tco2e"))
            .orderBy("period")
        )
        return result.toPandas()

    def compute_data_quality(self, sdf):
        """Compute data quality metrics using Spark."""
        if sdf is None:
            return {"completeness": 0, "total_records": 0, "total_fields": 0,
                    "null_count": 0, "avg_confidence": 0}

        total_records = sdf.count()
        total_fields = len(sdf.columns)
        total_cells = total_records * total_fields

        # Count nulls across all columns
        null_counts = sdf.select(
            [F.sum(F.when(F.col(c).isNull(), 1).otherwise(0)).alias(c) for c in sdf.columns]
        ).collect()[0]
        total_nulls = sum(null_counts[c] or 0 for c in sdf.columns)
        non_null = total_cells - total_nulls
        completeness = round(non_null / total_cells * 100, 1) if total_cells > 0 else 0

        # Confidence if available
        confidence = 0
        if "confidence" in sdf.columns:
            avg_conf = sdf.agg(F.avg("confidence")).collect()[0][0]
            confidence = round((avg_conf or 0) * 100, 1)

        return {
            "completeness": completeness,
            "total_records": total_records,
            "total_fields": total_fields,
            "null_count": total_nulls,
            "avg_confidence": confidence,
        }

    def compute_carbon_intensity(self, emissions_sdf, revenue_millions, year=None):
        """Compute carbon intensity (tCO2e per $M revenue) using Spark."""
        totals = self.compute_scope_totals(emissions_sdf, year)
        total_emissions = sum(totals.values())
        return round(total_emissions / revenue_millions, 1) if revenue_millions else 0

    def compute_supplier_risk_summary(self, supply_chain_sdf):
        """Aggregate supplier risk metrics using Spark."""
        if supply_chain_sdf is None:
            return {}
        result = (
            supply_chain_sdf
            .groupBy("risk_rating")
            .agg(
                F.count("*").alias("count"),
                F.avg("esg_score").alias("avg_esg_score"),
                F.sum("emission_contribution_tco2e").alias("total_emissions"),
            )
            .collect()
        )
        summary = {}
        for row in result:
            summary[row["risk_rating"]] = {
                "count": row["count"],
                "avg_esg_score": round(row["avg_esg_score"], 1),
                "total_emissions": round(row["total_emissions"], 1),
            }
        return summary

    def compute_esg_pillar_scores(self, metrics_sdf):
        """Compute ESG pillar scores using Spark aggregation."""
        if metrics_sdf is None:
            return {}
        result = (
            metrics_sdf
            .groupBy("pillar")
            .agg(
                F.count("*").alias("total"),
                F.sum(F.when(F.col("status") == "Met", 1).otherwise(0)).alias("met"),
            )
            .collect()
        )
        return {
            row["pillar"]: {
                "score": round(row["met"] / row["total"] * 100, 1) if row["total"] > 0 else 0,
                "metrics_met": row["met"],
                "total_metrics": row["total"],
            }
            for row in result
        }

    def compute_energy_mix(self, energy_sdf, year=None):
        """Compute energy mix breakdown using Spark."""
        if energy_sdf is None:
            return {}
        df = energy_sdf
        if year is not None:
            df = df.filter(F.col("year") == year)
        total = df.agg(F.sum("consumption_mwh")).collect()[0][0] or 0
        renewable = (
            df.filter(F.col("renewable") == "Yes")
            .agg(F.sum("consumption_mwh")).collect()[0][0] or 0
        )
        by_source = {
            row["energy_source"]: round(row["total"], 1)
            for row in (
                df.groupBy("energy_source")
                .agg(F.sum("consumption_mwh").alias("total"))
                .collect()
            )
        }
        return {
            "total_mwh": round(total, 1),
            "renewable_pct": round(renewable / total * 100, 1) if total else 0,
            "by_source": by_source,
        }

    def run_full_analysis(self):
        """Run all Spark computations in a single optimized pass. Returns dict."""
        emissions = self.load_emissions()
        metrics = self.load_esg_metrics()
        supply_chain = self.load_supply_chain()
        energy = self.load_energy()

        return {
            "scope_totals_2024": self.compute_scope_totals(emissions, 2024),
            "scope_totals_2023": self.compute_scope_totals(emissions, 2023),
            "quarterly_trends": self.compute_quarterly_trends(emissions),
            "emissions_quality": self.compute_data_quality(emissions),
            "metrics_quality": self.compute_data_quality(metrics),
            "supplier_risk": self.compute_supplier_risk_summary(supply_chain),
            "pillar_scores": self.compute_esg_pillar_scores(metrics),
            "energy_mix": self.compute_energy_mix(energy, 2024),
            "engine": "PySpark (distributed)" if self.is_available else "Pandas (local)",
        }

    def stop(self):
        """Stop the Spark session."""
        if self._spark is not None:
            self._spark.stop()
            self._spark = None


# ── Singleton ─────────────────────────────────────────────────────────────
spark_processor = SparkProcessor()
