"""Agent 1: Data Collector — Auto-discovers and ingests ESG data with quality scoring."""
import pandas as pd
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from utils.data_processing import (
    load_emissions, load_esg_metrics, load_supply_chain,
    load_energy, load_waste, load_diversity, compute_data_quality,
)


class DataCollectorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Data Collector",
            description="Auto-discovers, ingests, and validates ESG data from multiple sources.",
        )

    def execute(self, uploaded_files=None, **kwargs):
        self.log("Starting autonomous data collection")
        datasets = {}
        quality_scores = {}

        # Load all sample datasets
        sources = {
            "emissions": load_emissions,
            "esg_metrics": load_esg_metrics,
            "supply_chain": load_supply_chain,
            "energy": load_energy,
            "waste": load_waste,
            "diversity": load_diversity,
        }

        for name, loader in sources.items():
            df = loader()
            if not df.empty:
                datasets[name] = df
                quality = compute_data_quality(df)
                quality_scores[name] = quality
                self.log(f"Loaded {name}: {quality['total_records']} records, "
                         f"completeness={quality['completeness']}%")

        # Process uploaded files if any
        if uploaded_files:
            for file_name, file_data in uploaded_files.items():
                try:
                    if file_name.endswith(".csv"):
                        df = pd.read_csv(file_data)
                    elif file_name.endswith(".json"):
                        df = pd.read_json(file_data)
                    else:
                        continue
                    datasets[file_name] = df
                    quality_scores[file_name] = compute_data_quality(df)
                    self.log(f"Ingested uploaded file: {file_name}")
                except Exception as e:
                    self.log(f"Error processing {file_name}: {e}")

        # Compute overall quality
        overall_completeness = 0
        overall_confidence = 0
        if quality_scores:
            overall_completeness = sum(
                q["completeness"] for q in quality_scores.values()
            ) / len(quality_scores)
            confidence_vals = [q["avg_confidence"] for q in quality_scores.values() if q["avg_confidence"] > 0]
            overall_confidence = sum(confidence_vals) / len(confidence_vals) if confidence_vals else 0

        # AI-powered quality classification
        quality_issues = self._classify_quality_issues(quality_scores)

        # Publish validated data to shared state
        for name, df in datasets.items():
            state_manager.publish(f"validated_{name}", df.to_dict(), self.name)

        results = {
            "datasets_loaded": len(datasets),
            "total_records": sum(len(df) for df in datasets.values()),
            "quality_scores": quality_scores,
            "overall_completeness": round(overall_completeness, 1),
            "overall_confidence": round(overall_confidence, 1),
            "quality_issues": quality_issues,
            "dataset_names": list(datasets.keys()),
        }

        state_manager.publish("data_collection_results", results, self.name)
        return results

    def _classify_quality_issues(self, quality_scores):
        issues = []
        for name, quality in quality_scores.items():
            if quality["completeness"] < 90:
                severity = self.hf.classify(
                    f"Data completeness for {name} is {quality['completeness']}% with {quality['null_count']} missing values",
                    ["critical issue", "moderate concern", "minor issue"],
                )
                top_label = max(severity, key=severity.get)
                issues.append({
                    "dataset": name,
                    "issue": f"Completeness below threshold ({quality['completeness']}%)",
                    "severity": top_label,
                    "null_count": quality["null_count"],
                })

            if quality["avg_confidence"] > 0 and quality["avg_confidence"] < 75:
                issues.append({
                    "dataset": name,
                    "issue": f"Low confidence scores (avg: {quality['avg_confidence']}%)",
                    "severity": "moderate concern",
                    "null_count": 0,
                })
        return issues
