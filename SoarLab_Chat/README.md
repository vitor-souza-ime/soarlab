# SoarLab Chat v3.1 — Native Soar Cognitive Memory Laboratory

An English-language, smartphone-friendly Flask application for educational robotics. It uses **Soar 9.6.5 through the `soar-sml` Python package**. No simulated cognitive backend or LLM is used for memory responses.

## Cognitive corpus (initial release)

| Memory | Initial records | Implementation | Verification |
|---|---:|---|---|
| Procedural | **108 distinct scenario-response rules** | Individually compiled `sp` productions inside `agents/chat.soar` (120 total productions, including infrastructure rules) | Agent must issue a `^reply` via a matching native production |
| Semantic | **124 concept definitions** | SMem receives each concept via a native `^store-new` command | Exact read-after-write using native SMem query for every concept |
| Episodic | **120 distinct synthetic educational events** | Real Soar working-memory states encoded by native EpMem | Exact cue-based retrieval for every seeded experience |

The JSON files are **seed descriptions**, not the cognitive memory databases themselves. Procedural catalog entries are implemented as native productions, not read as facts from a Python dictionary. Initial episode descriptions are simulated classroom scenarios, **not actual robot field observations**. The native EpMem may contain additional internal episodes beyond the 120 verified pedagogical events.

## Quick start: Windows (the machine with Soar installed)

Use the same Python environment where `import soar_sml` already works.

```powershell
python -m pip install -r requirements.txt
python -c "import soar_sml; print(soar_sml.__file__)"
python diagnostico_soar.py
python app.py
```

Open: **http://127.0.0.1:5000**

The first startup verifies **244 individual SMem/EpMem seed records**. It may take noticeably longer than v2.1. Progress is printed every 25 verified items. If any native write/read check fails, the application refuses to start instead of inventing a success result. On initial use, please run `python diagnostico_soar.py` first; the Python unit tests do **not** execute a real Soar kernel.

### Smartphone access

1. Connect your phone and PC to the same trusted Wi-Fi network.
2. Use `ipconfig` to find the PC's IPv4 address.
3. Run `python app.py --lan`.
4. Open `http://YOUR_PC_IP:5000` on the phone.

This LAN server has no login or user authorization. It must **not** be exposed to the public internet.


## Automated verification and experiments (new in v3.1)

You do **not** need to test the 352 seeded memory entries manually or repeat the 48 evaluation questions by hand. Use the unattended native Soar runner:

```powershell
python run_all_tests.py --quick
python run_all_tests.py --full
```

The quick mode audits all 352 entries and records 48 benchmark questions. The full mode audits all entries, then measures 48 questions × 15 repetitions × 5 seed blocks in fresh Soar instances, with warm-ups excluded. Each completed seed block generates eight figures. Output includes per-record `native_memory_audit.csv`, `combined_raw.csv`, `summary_by_memory.csv`, `automation_manifest.json` and the usual per-run raw data and figures. This additional script is **not** a replacement for running the real Soar kernel on Windows.

Read [AUTOMATED_TESTING.md](AUTOMATED_TESTING.md) for commands and scientific caveats.

## Asking questions and teaching

The English parser recognizes registered aliases, controlled paraphrases, selected procedural requests, and basic deterministic fuzzy matches. It does not possess human-level natural-language understanding. Its **only** role is converting English text to a symbolic Soar `intent` and `topic`; the description/answer is returned through `^reply` from Soar.

### Semantic questions

- `What is the NAO robot?`
- `Tell me about the laser scanner.`
- `Explain SLAM.`
- `What is ROS 2?`
- `What is an occupancy grid?`
- `What is a robot gripper?`

### Procedural questions

- `What should the robot do if the battery is low in a classroom demonstration?`
- `How should the robot react when an obstacle is close in a classroom demonstration?`
- `What should the robot do if the emergency stop is triggered in a classroom demonstration?`

### Episodic questions

- `Do you remember an obstacle?`
- `What happened with the battery earlier?`
- `Do you remember a camera event?`
- `What happened during navigation before?`

The question panel contains **48 fixed questions** with reference memory and topic labels. The procedural catalog has 108 additional scenario questions and aliases in `data/procedural_catalog.json`.

### Teach something unknown

1. Ask `What is a tactile sensor array?`. The initial corpus intentionally does not include this exact concept.
2. Click **Teach a new concept**; enter `Tactile sensor array` and an English definition (at least 10 characters). For example: `A tactile array measures contact forces at multiple locations on a robot surface.`
3. Optionally add aliases such as `tactile matrix; multi-point touch sensor`.
4. Save. The application verifies both native SMem storage and immediate retrieval **before** showing a success notification.
5. Ask again `What is a tactile sensor array?` and then `Explain the tactile matrix.`

For episodic teaching, use **Add an experience**, select an English event category and provide an event description. A successful confirmation means an **exact native EpMem cue** matched the recorded event. It does not imply generalization or reasoning about unseen experiences.

Successful additions are journaled in `data/learned_facts.jsonl` and `data/learned_experiences.jsonl` for reinstatement on restart. These files support persistence but **do not replace** native memories.

## Which questions generate the figures?

There are **two separate benchmark data sources** selected in the interface:

- **Fixed evaluation corpus (recommended for an article):** replays the same 48 predefined English questions and controlled paraphrases for every repetition. It does **not** automatically use questions typed in the chatbot. Accuracy is evaluated against the corpus's authored memory/topic labels and native retrieval status.
- **Current chat questions (replay):** takes up to the 100 most recent chat questions that were sent to the native agent, then repeats them. It measures **replay agreement** against the agent/parser's original session outcome. This is **not independently labeled accuracy**. The user's original questions are preserved in the exported raw CSV.

A chat conversation can change the currently active native memories through teaching. Even the fixed benchmark will therefore use the **current memory state**, so run publication experiments from a clean, documented initialization when possible.

The benchmark has a repetition limit of 15 per run. For the main article, collect several independent runs using distinct shuffle seeds and documented restart/warm-up procedures (see `ARTICLE_EXPERIMENT_PROTOCOL.md`).

## Benchmark files and eight charts

The **Benchmark · 8 figures** control exports a run directory under `results/benchmark_.../` containing:

- `raw.csv` — individual native Soar queries with timing, decisions, counters, parser method, status and reference labels.
- `metadata.json` — mode, source corpus sizes, number of repetitions, seed, summary, warnings and verification flags.
- `01_latency_distribution.png` — boxplots of the measured Soar response time.
- `02_median_p95.png` — median and 95th-percentile response time.
- `03_accuracy_or_agreement.png` — fixed-set accuracy or session replay agreement.
- `04_latency_over_queries.png` — response-time sequence plot.
- `05_native_memory_queries.png` — observed native SMem and EpMem counter increments (separately).
- `06_paraphrase_accuracy.png` — controlled-parser method scores.
- `07_soar_decision_cycles.png` — Soar decision cycles needed for replies.
- `08_e2e_vs_soar.png` — Python+SML end-to-end versus measured SML/Soar call time.

The `latency_soar_ms` field includes SML calls and query orchestration; it is **not** an isolated microbenchmark of native memory retrieval internals. The end-to-end latency excludes HTTP transport to the mobile browser.

`python regenerar_graficos.py` regenerates all eight figures from the existing complete `raw.csv` without re-running Soar. A partial or non-native result is rejected.

## Scientific and technical limits

- Predefined paraphrases are already recognized by the deterministic English parser. Testing them does **not** prove generalization to arbitrary natural language.
- SMem facts, EpMem episodes, and procedural rules are **different representations** and should not be treated as identical statistical units.
- The 120 episodes are **synthetic educational scenarios** introduced into native Soar working memory; they are not authentic historical robot missions.
- Session replay agreement is **not** independently judged correctness.
- No educational benefit can be claimed without a separate student study (potentially requiring ethical approval).
- Python tests evaluate the source data, classifier, static production text, and plots. **The native 9.6.5 kernel was not available on the packaging machine.** The diagnostic on your Windows environment is necessary to validate correct native execution.

See `ARTICLE_EXPERIMENT_PROTOCOL.md`, `EVALUATION_QUESTIONS.md`, and `tests/test_app.py`.

References: [Soar Semantic Memory](https://soar.eecs.umich.edu/soar_manual/06_SemanticMemory/), [Soar Episodic Memory](https://soar.eecs.umich.edu/soar_manual/07_EpisodicMemory/), [Soar 9.6.5 release](https://soar.eecs.umich.edu/downloads/soar/latest/).
