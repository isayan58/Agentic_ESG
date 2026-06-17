"""Agent 1: Data Collector — Auto-discovers and ingests ESG data with quality scoring."""
import pandas as pd
from core.base_agent import BaseAgent
from core.channels import Channel, dataset_channel, validated_channel
from core.state_manager import state_manager
from core.company_config import company_cfg
from utils.data_processing import (
    load_emissions, load_esg_metrics, load_supply_chain,
    load_energy, load_waste, load_diversity, load_financials,
    compute_data_quality, _norm_cols,
)
from utils.connectors import get_all_connectors


class DataCollectorAgent(BaseAgent):
    # Per-schema validated_*/dataset_* channels are still published inline
    # mid-execute (we publish 14+ side channels, one per ingested schema).
    # output_channel only handles the canonical end-of-run summary that
    # downstream agents subscribe to.
    output_channel = Channel.DATA_COLLECTION

    def __init__(self):
        super().__init__(
            name="Data Collector",
            description="Auto-discovers, ingests, and validates ESG data from multiple sources.",
        )
        self.connectors = get_all_connectors()
        self.connector_statuses = {}
        self.missing_data_alerts = []

    def execute(self, uploaded_files=None, use_connectors=True,
                connection_manager=None, use_cache=False, **kwargs):
        self.log("Starting autonomous data collection")
        datasets = {}
        quality_scores = {}

        # ── Phase 0: Fetch from real data sources (if configured) ──
        if connection_manager is not None and connection_manager.has_sources():
            self.log("Fetching from real data sources...")
            try:
                # use_cache=True reuses per-source DataFrames when the
                # source config signature is unchanged, so unchanged
                # Snowflake queries don't re-execute on every Run.
                try:
                    by_schema = connection_manager.fetch_all_by_schema(use_cache=use_cache)
                except TypeError:
                    by_schema = connection_manager.fetch_all_by_schema()
                for schema_name, df in by_schema.items():
                    if not df.empty:
                        key = f"real_{schema_name}"
                        datasets[key] = _norm_cols(df)
                        quality = compute_data_quality(df, source_tier="real")
                        quality_scores[key] = quality
                        self.log(f"Real source [{schema_name}]: {len(df)} records, "
                                 f"completeness={quality['completeness']}%")
            except Exception as e:
                self.log(f"Real source error: {e}")

        # ── Phase 1: Load local sample datasets ──
        sources = {
            "emissions": load_emissions,
            "esg_metrics": load_esg_metrics,
            "supply_chain": load_supply_chain,
            "energy": load_energy,
            "waste": load_waste,
            "diversity": load_diversity,
            "financials": load_financials,
        }

        for name, loader in sources.items():
            df = loader()
            if not df.empty:
                datasets[name] = df
                quality = compute_data_quality(df, source_tier="sample")
                quality_scores[name] = quality
                self.log(f"Loaded {name}: {quality['total_records']} records, "
                         f"completeness={quality['completeness']}%")

        # ── Phase 2: Auto-discover from enterprise connectors (ERP, HR, IoT, etc.) ──
        if use_connectors:
            self.log("Auto-discovering enterprise data sources...")
            for conn_key, connector in self.connectors.items():
                try:
                    df = connector.fetch()
                    if df is not None and not df.empty:
                        datasets[f"connector_{conn_key}"] = _norm_cols(df)
                        quality_scores[f"connector_{conn_key}"] = compute_data_quality(df, source_tier="connector")
                        self.log(f"Connected: {connector.name} — {len(df)} records ingested")
                    self.connector_statuses[conn_key] = connector.get_status()
                except Exception as e:
                    self.connector_statuses[conn_key] = {
                        **connector.get_status(), "status": "error", "error": str(e)
                    }
                    self.log(f"Connector error ({connector.name}): {e}")

        # ── Phase 3: Process uploaded files ──
        if uploaded_files:
            from utils.schema_mapper import auto_detect_schema, suggest_column_mapping, apply_column_mapping
            _canonical_schema_names = [
                "emissions", "esg_metrics", "supply_chain",
                "energy", "waste", "diversity", "financials",
                # Peer benchmarking schemas (optional — no missing-data alerts)
                "peer_companies", "peer_financials", "peer_esg",
                "peer_metrics", "peer_benchmark",
            ]
            for file_name, file_data in uploaded_files.items():
                try:
                    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
                    if ext == "csv":
                        df = _norm_cols(pd.read_csv(file_data))
                    elif ext in ("xlsx", "xls"):
                        df = _norm_cols(pd.read_excel(file_data))
                    elif ext == "json":
                        df = _norm_cols(pd.read_json(file_data))
                    else:
                        self.log(f"Skipping unsupported format: {file_name}")
                        continue

                    # Try to map to a canonical schema so downstream agents
                    # receive real data instead of sample data.
                    detected = auto_detect_schema(df)
                    if detected and detected in _canonical_schema_names:
                        mapping = suggest_column_mapping(df, detected)
                        mapped_df = apply_column_mapping(df, mapping, detected)
                        # Store under the canonical name (real_ prefix so
                        # _resolve_canonical_datasets picks it over sample data).
                        key = f"real_{detected}"
                        datasets[key] = mapped_df if not mapped_df.empty else df
                        self.log(f"Uploaded file '{file_name}' mapped to schema '{detected}' ({len(df)} rows)")
                    else:
                        # Store by filename as a supplementary dataset.
                        key = file_name
                        datasets[key] = df
                        self.log(f"Ingested uploaded file: {file_name} (schema undetected, stored as-is)")

                    quality_scores[key] = compute_data_quality(datasets[key], source_tier="real")
                except Exception as e:
                    self.log(f"Error processing {file_name}: {e}")

        # ── Phase 4: Auto-discovery — proactive missing data alerts ──
        self.missing_data_alerts = self._detect_missing_data(datasets, quality_scores)
        for alert in self.missing_data_alerts:
            self.log(f"ALERT: {alert['message']}")

        # Canonical datasets are what downstream analytics should consume.
        canonical_datasets = self._resolve_canonical_datasets(datasets)

        # ── Phase 5: Compute overall quality ──
        overall_completeness = 0
        overall_confidence = 0
        if quality_scores:
            overall_completeness = sum(
                q["completeness"] for q in quality_scores.values()
            ) / len(quality_scores)
            confidence_vals = [q["avg_confidence"] for q in quality_scores.values() if q["avg_confidence"] > 0]
            overall_confidence = sum(confidence_vals) / len(confidence_vals) if confidence_vals else 0

        # ── Phase 6: AI-powered quality classification ──
        quality_issues = self._classify_quality_issues(quality_scores)

        # ── Phase 7: Assign verifiable trust / confidence scoring ──
        confidence_scores = self._compute_confidence_scores(datasets, quality_scores)

        # ── Phase 8: Claude-powered specific data-quality gap analysis ──
        # Falls back to the legacy HF bullets on missing API key /
        # network failure. The structured `gap_analysis` powers the new
        # field-level table on the Data Collector page.
        canonical_summary = {
            name: {"source": payload["source"], "records": len(payload["data"])}
            for name, payload in canonical_datasets.items()
        }
        from utils.gap_analyzer import analyze_data_quality_gaps
        gap_analysis = analyze_data_quality_gaps(
            quality_scores,
            self.missing_data_alerts,
            canonical_datasets=canonical_summary,
            connector_statuses=self.connector_statuses,
            fallback_summary=lambda: self._generate_data_quality_summary(
                quality_scores, self.missing_data_alerts
            ),
        )
        data_quality_summary = gap_analysis.get("recommendations") or self._generate_data_quality_summary(
            quality_scores, self.missing_data_alerts
        )

        # Publish validated data to shared state
        for name, df in datasets.items():
            state_manager.publish(validated_channel(name), df.to_dict(), self.name)
        for schema_name, payload in canonical_datasets.items():
            state_manager.publish(dataset_channel(schema_name), payload["data"], self.name)

        results = {
            "datasets_loaded": len(datasets),
            "total_records": sum(len(df) for df in datasets.values()),
            "quality_scores": quality_scores,
            "overall_completeness": round(overall_completeness, 1),
            "overall_confidence": round(overall_confidence, 1),
            "quality_issues": quality_issues,
            "dataset_names": list(datasets.keys()),
            "canonical_datasets": canonical_summary,
            "connector_statuses": self.connector_statuses,
            "missing_data_alerts": self.missing_data_alerts,
            "confidence_scores": confidence_scores,
            "data_quality_summary": data_quality_summary,
            "gap_analysis": gap_analysis,
        }

        return results

    def _generate_data_quality_summary(self, quality_scores, missing_data_alerts):
        prompt = (
            f"You are an ESG data quality analyst. Summarize the current data collection status "
            f"for the company, including dataset completeness, confidence, and any missing or low-quality data alerts. "
            f"Quality scores: {quality_scores}. "
            f"Missing data alerts: {[alert['message'] for alert in missing_data_alerts]}. "
            f"Provide 3 concise recommendations to improve the data foundation for ESG reporting."
        )
        raw = self.hf.generate_text(prompt, max_tokens=220)
        bullets = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return bullets if bullets else [raw.strip()]

    def _detect_missing_data(self, datasets, quality_scores):
        """Proactively detect gaps before they compromise reporting."""
        alerts = []
        t = company_cfg.thresholds
        expected = {
            "emissions": "Scope 1/2/3 Emissions data — required for BRSR, CSRD, GRI",
            "esg_metrics": "ESG KPI metrics — required for all framework reporting",
            "supply_chain": "Supply chain data — required for Scope 3 and CSRD S2",
            "energy": "Energy consumption data — required for BRSR, GRI 302, SASB",
            "waste": "Waste management data — required for BRSR, GRI 306",
            "diversity": "Workforce diversity data — required for BRSR, CSRD S1, GRI 405",
            "financials": "Financial data — required for ESG ROI, J-Curve, and KPI correlations",
        }
        for key, desc in expected.items():
            if key not in datasets:
                alerts.append({
                    "severity": "critical",
                    "dataset": key,
                    "message": f"Missing: {desc}",
                    "action": f"Connect data source or upload {key} dataset",
                })
            elif quality_scores.get(key, {}).get("completeness", 0) < t.completeness_warning:
                comp = quality_scores[key]["completeness"]
                alerts.append({
                    "severity": "warning",
                    "dataset": key,
                    "message": f"Low completeness ({comp}%): {desc.split('—')[0].strip()}",
                    "action": f"Review and fill missing fields in {key}",
                })
        return alerts

    def _resolve_canonical_datasets(self, datasets):
        """Choose one canonical dataset per schema for downstream analytics."""
        canonical = {}
        schema_names = [
            "emissions", "esg_metrics", "supply_chain",
            "energy", "waste", "diversity", "financials",
            # Peer benchmarking schemas
            "peer_companies", "peer_financials", "peer_esg",
            "peer_metrics", "peer_benchmark",
        ]

        for schema_name in schema_names:
            if f"real_{schema_name}" in datasets and not datasets[f"real_{schema_name}"].empty:
                canonical[schema_name] = {
                    "source": "real_source",
                    "data": datasets[f"real_{schema_name}"].copy(),
                }
            elif schema_name in datasets and not datasets[schema_name].empty:
                canonical[schema_name] = {
                    "source": "sample_dataset",
                    "data": datasets[schema_name].copy(),
                }

        return canonical

    def _compute_confidence_scores(self, datasets, quality_scores):
        """Assign verifiable trust scores per dataset for audit readiness."""
        scores = {}
        t = company_cfg.thresholds
        cw = company_cfg.confidence_weights

        for name in datasets:
            q = quality_scores.get(name, {})
            completeness = q.get("completeness", 0)
            raw_confidence = q.get("avg_confidence", 0)

            # Source trust bonus
            if name.startswith("real_"):
                source_bonus = t.source_bonus_real
            elif name.startswith("connector_"):
                source_bonus = t.source_bonus_connector
            else:
                source_bonus = t.source_bonus_sample

            weighted = round(
                completeness * cw.completeness +
                raw_confidence * cw.raw_confidence +
                source_bonus +
                t.freshness_bonus * cw.freshness, 1
            )
            weighted = min(100, weighted)

            level = ("High" if weighted >= t.confidence_high
                     else ("Medium" if weighted >= t.confidence_medium else "Low"))
            scores[name] = {
                "score": weighted,
                "level": level,
                "audit_ready": weighted >= t.confidence_audit_ready,
            }
        return scores

    def _classify_quality_issues(self, quality_scores):
        issues = []
        t = company_cfg.thresholds
        for name, quality in quality_scores.items():
            if quality["completeness"] < t.quality_issue_completeness:
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

            if quality["avg_confidence"] > 0 and quality["avg_confidence"] < t.low_confidence_alert:
                issues.append({
                    "dataset": name,
                    "issue": f"Low confidence scores (avg: {quality['avg_confidence']}%)",
                    "severity": "moderate concern",
                    "null_count": 0,
                })
        return issues
