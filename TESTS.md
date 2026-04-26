# Test Cases & Results

Documentation of the automated test suite covering the ETL pipeline,
connection layer, and pipeline-refresh helper.

- **Framework:** `pytest` 9.0.3 on CPython 3.12.2
- **Plugins:** `pluggy` 1.6.0, `anyio` 4.13.0
- **Rootdir:** `trusting-maxwell/`
- **Run:** `.venv/bin/python -m pytest tests/ -q`
- **Latest result:** ✅ **64 passed in 1.01s**

---

## How to run locally

```bash
# Fast pass (summary only)
.venv/bin/python -m pytest tests/ -q

# Verbose (one line per test)
.venv/bin/python -m pytest tests/ -v

# With per-test timings
.venv/bin/python -m pytest tests/ --durations=0 -q

# A single file
.venv/bin/python -m pytest tests/test_pipeline_refresh.py -v
```

## Test layout

```
tests/
├── conftest.py                           # shared fixtures
├── test_connection_manager.py            # 33 unit tests
├── test_datacollector_integration.py     #  7 end-to-end tests
└── test_pipeline_refresh.py              # 24 unit tests
```

### Shared fixtures (`conftest.py`)

| Fixture | What it does |
|---|---|
| `fake_st` | Installs a `FakeStreamlit` into `utils.pipeline_refresh.st`. Records every `st.warning` / `st.caption` / `st.toast` call so tests can assert on them. Also resets the `state_manager` singleton before & after each test. |
| `register_fake_connector` | Returns a factory that registers an `InMemoryConnector` into `utils.real_connectors.REAL_CONNECTORS` under a unique connector type. The factory yields `(ctype, connector_instance)` so tests can count `fetch_calls` and force failures. Restores the original registry on teardown. |
| `identity_mapping` | Monkey-patches `apply_column_mapping` to a pass-through so tests focus on caching / fetch semantics instead of schema coercion. |

---

## 1. `test_connection_manager.py` — 33 tests

Unit tests for the registry, signature helper, and per-source cache that sit
inside `utils/connection_manager.py`. No network traffic: every test drives
a `ConnectionManager` through the `InMemoryConnector` fake.

### 1.1 `TestSignatureHelper` — `_signature()` primitives (6 tests)

| # | Test | What it proves |
|---|---|---|
| 1 | `test_deterministic_for_equal_inputs` | Same inputs always produce the same hash. |
| 2 | `test_differs_when_value_changes` | A single value edit changes the hash. |
| 3 | `test_order_independent_for_dicts` | Dict key order doesn't affect the hash (sorted internally). |
| 4 | `test_bytes_hashed_with_full_sha256` | `bytes` payloads hash via full SHA-256; two different 4-byte inputs collide-safely. |
| 5 | `test_bytes_signature_length_suggests_full_sha256` | Hash length is 64 hex chars — regression guard against truncated 16-char hashes. |
| 6 | `test_handles_non_json_serialisable_via_repr` | Arbitrary objects fall back to `repr()` for stable signatures. |

### 1.2 `TestRegistry` — add / list / remove (4 tests)

| # | Test | What it proves |
|---|---|---|
| 7 | `test_add_source_initialises_cache_fields` | `add_source()` initialises `_cached_signature` & `_cached_df` to `None` and status to `"configured"`. |
| 8 | `test_list_sources_hides_underscore_cache_fields` | `list_sources()` never leaks private `_cached_*` fields. |
| 9 | `test_remove_source_returns_bool` | `True` on first remove, `False` on second. |
| 10 | `test_has_sources_tracks_state` | Toggles correctly through add → remove. |

### 1.3 `TestSignatures` — source + manager signatures (8 tests)

| # | Test | What it proves |
|---|---|---|
| 11 | `test_source_signature_stable` | Same source → same 64-hex signature. |
| 12 | `test_source_signature_empty_for_unknown` | Returns `""` for unknown IDs (no KeyError). |
| 13 | `test_signature_changes_when_config_changes` | User editing a query flips the signature. |
| 14 | `test_signature_changes_when_schema_changes` | Rebinding `target_schema` flips the signature. |
| 15 | `test_signature_changes_when_mapping_changes` | Column mapping changes flip the signature. |
| 16 | `test_signature_changes_when_connector_type_changes` | Switching connector (`delta_lake` → `aws_s3`) flips the signature. |
| 17 | `test_sources_signature_order_independent` | Two managers with the same sources in different add order hash identically. |
| 18 | `test_file_bytes_detected_as_different` | Same-length but different upload bytes flip the signature (full SHA-256 of payload). |

### 1.4 `TestFetchAndCache` — per-source cache (10 tests)

| # | Test | What it proves |
|---|---|---|
| 19 | `test_fetch_source_unknown_raises` | `fetch_source("missing")` raises `KeyError`. |
| 20 | `test_fetch_source_returns_mapped_df` | Columns + row count propagate; `status="active"`, `last_row_count` set. |
| 21 | `test_cache_hit_when_signature_matches` | Second fetch with unchanged config does **not** re-call connector. |
| 22 | `test_cache_miss_when_signature_changes` | Editing config busts cache — next call re-fetches. |
| 23 | `test_cache_disabled_always_refetches` | `use_cache=False` bypasses cache every time. |
| 24 | `test_cache_returns_independent_copy` | Mutating the returned DataFrame doesn't poison the cache. |
| 25 | `test_invalidate_cache_single` | `invalidate_cache(id)` forces next fetch to re-query. |
| 26 | `test_invalidate_cache_all` | `invalidate_cache()` (no arg) busts every source. |
| 27 | `test_re_registering_source_clears_cache` | `add_source()` overwriting an existing ID resets the cache. |
| (see 1.5) | `test_fetch_all_forwards_use_cache` | `fetch_all(use_cache=True)` propagates into per-source cache (counted in next group). |

### 1.5 `TestFetchAllAndErrors` — orchestration & errors (5 tests)

| # | Test | What it proves |
|---|---|---|
| 28 | `test_fetch_all_returns_empty_for_failing_source` | Failing source returns an empty DF while healthy sources succeed; status becomes `"error"`. |
| 29 | `test_source_errors_only_returns_errored` | `source_errors()` shows only failed sources with the failure message. |
| 30 | `test_fetch_all_by_schema_concatenates_multi_source` | Two sources targeting `emissions` are concatenated into one DataFrame. |
| 31 | `test_fetch_all_by_schema_skips_empty_sources` | Failing source doesn't pollute the concatenated schema result. |
| 32 | `test_fetch_all_forwards_use_cache` | Manager-level cache flag reaches per-source fetch. |
| 33 | `test_fetch_all_by_schema_forwards_use_cache` | Same for the by-schema path. |

---

## 2. `test_datacollector_integration.py` — 7 tests

End-to-end: `refresh_real_data()` → real `ConnectionManager` → real
`DataCollectorAgent` → real `state_manager`. The connector is still a fake
in-memory one so no network is involved, but every other layer is production
code.

| # | Test | What it proves |
|---|---|---|
| 34 | `test_use_cache_prevents_remote_refetch` | `only_changed=True` with an unchanged source doesn't re-call the connector; calling again with `only_changed=False` (default) re-executes. |
| 35 | `test_config_edit_invalidates_cache` | Editing a source config (`"SELECT 1"` → `"SELECT 2"`) invalidates the cache — next refresh re-fetches even under `only_changed=True`. |
| 36 | `test_real_data_published_to_state_manager` | Refresh publishes a `dataset_emissions` channel with the expected rows. |
| 37 | `test_removing_real_only_source_drops_its_dataset` | A schema with no sample fallback (`peer_metrics`) loses its `dataset_*` channel when its only real source is removed. Neighbour channels untouched. |
| 38 | `test_removing_source_clears_stale_real_data` | After a real source is removed, its sentinel values don't linger in the published channel. (Samples have been retired, so the guarantee narrowed from "sample backfills" to "no stale leak".) |
| 39 | `test_failed_source_reported_and_warned` | A failing source shows up in `mgr.source_errors()`, in `result["errors"]`, and as an `st.warning` banner; healthy sources still publish their datasets. |
| 40 | `test_empty_conn_manager_does_not_publish_real_channels` | With no `conn_manager` in session state, `refresh_real_data()` returns `refreshed=False` and writes no `dataset_*` channels. |

---

## 3. `test_pipeline_refresh.py` — 24 tests

Unit tests for `utils/pipeline_refresh.py` using `StubDataCollector` and
`StubConnectionManager` so we can drive every branch deterministically.

### 3.1 `TestRefreshRealData` — main entry point (13 tests)

| # | Test | What it proves |
|---|---|---|
| 41 | `test_no_sources_returns_reason_no_sources` | Guest path: no `conn_manager` → `refreshed=False, reason="no_sources"`. |
| 42 | `test_no_conn_mgr_at_all` | Same contract when the session state key is entirely missing. |
| 43 | `test_with_sources_re_runs_data_collector` | Happy path: refresh calls DataCollector, returns `refreshed=True`, propagates `records`, `sources`, `signature`. |
| 44 | `test_only_changed_propagates_use_cache_true` | `only_changed=True` reaches the agent as `use_cache=True`. |
| 45 | `test_default_is_full_refresh` | Default `only_changed=False` → `use_cache=False` passed through. |
| 46 | `test_older_data_collector_without_use_cache` | If the agent's `run()` signature doesn't accept `use_cache`, we catch `TypeError` and retry without it. |
| 47 | `test_writes_session_state_keys` | Sets `_last_data_refresh`, `_last_data_refresh_records`, `_last_data_refresh_signature`, `_last_data_refresh_errors`. |
| 48 | `test_surfaces_source_errors_as_warnings` | Errors on the manager appear in `result["errors"]` and as `st.warning` banners with source ID + message. |
| 49 | `test_show_errors_false_suppresses_warnings` | `show_errors=False` opt-out stops banners from rendering. |
| 50 | `test_show_toast_renders_toast_on_success` | `show_toast=True` triggers the "Refreshed N source(s)" toast. |
| 51 | `test_clears_stale_state_manager_channels` | Pre-existing `dataset_*` and `validated_*` channels are wiped before re-publishing. Non-dataset channels are preserved. |
| 52 | `test_empty_manager_still_clears_stale_channels` | Regression: a manager with zero sources still clears stale channels and invokes the DataCollector so sample data can repopulate. |
| 53 | `test_reuses_existing_data_collector` | When a collector is already in session state, we don't re-instantiate — preserves the audit trail. |

### 3.2 `TestStampRefreshFromPipeline` — non-helper refresh path (2 tests)

| # | Test | What it proves |
|---|---|---|
| 54 | `test_writes_session_state_keys` | ESG Command Center's full-pipeline run can stamp freshness keys so every page's caption stays honest. |
| 55 | `test_works_without_conn_manager` | No-op safe when no manager is in session; signature resolves to `None`. |

### 3.3 `TestDataFreshnessCaption` — UI badge (6 tests)

| # | Test | What it proves |
|---|---|---|
| 56 | `test_renders_nothing_when_no_conn_manager` | Zero noise for guests. |
| 57 | `test_renders_nothing_when_no_sources` | Zero noise when the user has no registered sources. |
| 58 | `test_renders_prompt_when_sources_but_never_refreshed` | Shows "will be re-fetched next Run" instead of a timestamp. |
| 59 | `test_renders_ago_when_refreshed` | After a successful refresh, caption includes a relative timestamp ("sec ago" / "min ago"). |
| 60 | `test_renders_error_line_when_last_refresh_had_errors` | Second caption line names the failed source and warns about sample-data fallback. |
| 61 | `test_handles_bad_timestamp_gracefully` | Corrupt ISO timestamp falls back to "recently" instead of crashing. |

### 3.4 `TestSignatureFallback` — `_compute_sources_signature` (3 tests)

| # | Test | What it proves |
|---|---|---|
| 62 | `test_uses_manager_native_signature_when_available` | Delegates to `conn_mgr.sources_signature()` when present. |
| 63 | `test_falls_back_when_manager_lacks_method` | Legacy manager with only `list_sources()` still produces a 64-char hex signature. |
| 64 | `test_empty_string_when_list_sources_raises` | Broken manager raising from `list_sources()` yields `""` instead of propagating. |

---

## Result matrix

| Suite | File | Tests | Passed | Failed | Wall time (approx.) |
|---|---|---:|---:|---:|---:|
| Connection manager | `test_connection_manager.py` | 33 | 33 | 0 | ~0.02s |
| Data Collector integration | `test_datacollector_integration.py` | 7 | 7 | 0 | ~0.49s |
| Pipeline refresh | `test_pipeline_refresh.py` | 24 | 24 | 0 | ~0.03s |
| **Total** | | **64** | **64** | **0** | **~1.01s** |

### Slowest 9 tests (from `--durations=0`)

| Duration | Phase | Test |
|---:|---|---|
| 0.32s | setup | `test_use_cache_prevents_remote_refetch` |
| 0.20s | call  | `test_empty_conn_manager_does_not_publish_real_channels` |
| 0.09s | call  | `test_use_cache_prevents_remote_refetch` |
| 0.05s | call  | `test_removing_source_clears_stale_real_data` |
| 0.05s | call  | `test_config_edit_invalidates_cache` |
| 0.05s | call  | `test_removing_real_only_source_drops_its_dataset` |
| 0.02s | call  | `test_failed_source_reported_and_warned` |
| 0.02s | call  | `test_real_data_published_to_state_manager` |
| 0.01s | call  | `test_fetch_source_returns_mapped_df` |

All other tests run under 5ms and are hidden from the default durations report.

---

## Coverage map — what's *not* under automated test

These areas rely on manual smoke-tests today. Each has a ticket-style note
in `RUNBOOK.md` describing the manual verification step:

- **Per-user profile store** (`utils/profile_store.py`) — round-trip covered
  by the smoke-test script; no pytest file yet.
- **`CompanyConfig` thread-local proxy** (`core/company_config.py`) — verified
  via smoke-test (swap active config mid-call, confirm agents pick it up)
  but no dedicated unit test.
- **Concurrent-write retry loops** (`utils/user_store.py`, `utils/source_store.py`) —
  the retry path is exercised in manual multi-tab testing; no fault-injection
  test.
- **Rate limiter** (`utils/auth.py` `_check_rate_limit`) — trigger confirmed
  via smoke-test (11 rapid logins hit `RateLimitExceeded`); no pytest file
  yet.
- **HF Dataset persistence** — depends on a real HF token; guarded by graceful
  fallback to `data/` local store which the existing tests implicitly cover.
- **Streamlit page rendering** — no `streamlit.testing` harness in place;
  pages are verified end-to-end by running the app.

These gaps are intentional — the automated suite focuses on the data-plane
correctness (connections, caching, publication) where regressions are silent
and costly. UI / auth / persistence regressions surface immediately on deploy.
