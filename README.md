# LlamaExtract CI/CD Demo with Webhook Integration

A minimal Python project demonstrating three things:

1. **LlamaExtract** for structured data extraction (merchant name, date, total) from receipt PDFs
2. **CI/CD pipeline** (GitHub Actions) that re-runs extraction when the Pydantic schema changes in a PR, computes field-level accuracy against ground truth, and posts a PR comment with results and delta
3. **Webhook integration** built into extract.py -- when `WEBHOOK_URL` is set, extraction jobs include webhook configuration so LlamaExtract POSTs completion events to the configured endpoint

## Project Structure

```
demo-extract-webhook-cicd/
├── requirements.txt          # Python dependencies
├── .env.example              # Template for local env vars
├── .gitignore
├── data/
│   ├── invoice_1.pdf         # Sample receipt: generic store, 2019-01-02, $383.99
│   ├── invoice_2.pdf         # Sample receipt: Zara Kentpark, 2023-06-23, 1542.35 TL
│   └── invoice_3.pdf         # Sample receipt: Walmart, 1998-05-29, $61.64
├── schema.py                 # Pydantic model defining extraction schema
├── extract.py                # Run extraction on all PDFs, save results
├── evaluate.py               # Compare extraction results vs ground truth
├── ground_truth.json         # Ground truth data
├── metrics.json              # Baseline metrics (updated on merge to main)
├── results/                  # Extraction output (gitignored)
│   └── .gitkeep
└── .github/workflows/
    ├── extract-eval.yml      # PR evaluation workflow
    └── update-baseline.yml   # Post-merge baseline update workflow
```

## Prerequisites

- Python 3.11+
- A LlamaCloud API key ([get one here](https://cloud.llamaindex.ai/))

## Setup

Run the setup script:

```bash
./init.sh
```

Or set up manually:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your LLAMA_CLOUD_API_KEY
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LLAMA_CLOUD_API_KEY` | Yes | LlamaCloud API key for extraction |
| `WEBHOOK_URL` | No | Webhook endpoint URL for real-time extraction events |

## Usage

### Extract data from receipts

```bash
python extract.py
```

This uploads each PDF in `data/` to LlamaExtract, runs extraction with the schema from `schema.py`, and saves results to `results/extraction_output.json`.

### Initialize ground truth (first run)

```bash
python extract.py --init-ground-truth
```

Saves extraction output to `ground_truth.json` instead. Review and correct the values before committing.

### Evaluate extraction accuracy

```bash
python evaluate.py                    # Print results to stdout
python evaluate.py --output-markdown  # Also write results/pr_comment.md
```

Compares extraction results against ground truth, computes field-level accuracy, and optionally generates a markdown PR comment.

## CI/CD Pipeline

### PR Evaluation Workflow (`extract-eval.yml`)

Triggers on pull requests that modify `schema.py`:

1. Runs extraction with the updated schema
2. Evaluates accuracy against ground truth
3. Posts (or updates) a PR comment with results and delta vs baseline

### Baseline Update Workflow (`update-baseline.yml`)

Triggers on push to `main` when `schema.py` changes:

1. Re-runs extraction and evaluation
2. Commits updated `metrics.json` baseline

### GitHub Secrets

Add `LLAMA_CLOUD_API_KEY` as a repository secret in GitHub Settings > Secrets and variables > Actions.

## Webhook Integration

Webhook support is built into `extract.py`. When the `WEBHOOK_URL` environment variable is set, each extraction job includes webhook configuration so LlamaExtract POSTs completion events to the configured endpoint.

### Testing with webhook.site

1. Set `WEBHOOK_URL` in your `.env` file:
   ```
   WEBHOOK_URL=https://webhook.site/b87995d5-e449-4074-b311-e0deed2d34dc
   ```

2. Run extraction:
   ```bash
   python extract.py
   ```

3. Open the webhook URL in your browser to see the payloads:
   https://webhook.site/b87995d5-e449-4074-b311-e0deed2d34dc

The webhook fires `extract.success` or `extract.error` events for each invoice processed.

**Note:** Webhooks are not used in the CI pipeline -- `WEBHOOK_URL` is not set in GitHub Actions, so extraction uses polling only.
