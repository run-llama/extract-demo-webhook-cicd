"""Extract structured data from receipt PDFs using LlamaExtract."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from llama_cloud import AsyncLlamaCloud

from schema import InvoiceSchema


async def process_pdf(
    client: AsyncLlamaCloud,
    pdf_path: Path,
    webhook_url: str | None,
) -> tuple[str, dict]:
    """Process a single PDF and return (filename, result_dict)."""
    filename = pdf_path.name
    print(f"  [{filename}] Uploading...")
    with open(pdf_path, "rb") as f:
        file_obj = await client.files.create(file=f, purpose="extract")
    print(f"  [{filename}] Uploaded. File ID: {file_obj.id}")

    webhook_configurations = None
    if webhook_url:
        webhook_configurations = [
            {
                "webhook_url": webhook_url,
                "webhook_events": ["extract.success", "extract.error"],
                "webhook_output_format": "json",
            }
        ]
        print(f"  [{filename}] Webhook configured: {webhook_url}")

    print(f"  [{filename}] Starting extraction...")
    job = await client.extract.create(
        file_input=file_obj.id,
        configuration={
            "data_schema": InvoiceSchema.model_json_schema(),
            "extraction_target": "per_doc",
            "tier": "agentic",
        },
        webhook_configurations=webhook_configurations,
    )

    start_time = asyncio.get_event_loop().time()
    while job.status not in ("COMPLETED", "FAILED", "CANCELLED"):
        await asyncio.sleep(2)
        try:
            job = await client.extract.get(job.id)
        except Exception as e:
            print(f"  [{filename}] Warning: polling error ({e}), retrying...")
            continue

    elapsed = asyncio.get_event_loop().time() - start_time

    if job.status == "COMPLETED":
        result_data = job.extract_result
        if isinstance(result_data, list):
            result_data = result_data[0] if result_data else {}

        invoice = InvoiceSchema.model_validate(result_data or {})
        result = {
            "merchant_name": invoice.merchant_name,
            "date": invoice.date,
            "total": invoice.total,
        }
        print(f"  [{filename}] Completed in {elapsed:.1f}s: {result}")
        return filename, result
    else:
        print(f"  [{filename}] Error: extraction {job.status} after {elapsed:.1f}s")
        return filename, {"merchant_name": None, "date": None, "total": None}


async def main():
    """Run extraction on all PDFs in data/ directory concurrently."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="Extract data from receipt PDFs")
    parser.add_argument(
        "--init-ground-truth",
        action="store_true",
        help="Save output as ground_truth.json instead of results/extraction_output.json",
    )
    args = parser.parse_args()

    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        print("Error: LLAMA_CLOUD_API_KEY environment variable is not set.")
        print("Set it in your .env file or export it in your shell.")
        sys.exit(1)

    webhook_url = os.getenv("WEBHOOK_URL")
    client = AsyncLlamaCloud(api_key=api_key)

    data_dir = Path("data")
    pdf_files = sorted(data_dir.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in data/ directory.")
        results = {}
        success_count = 0
        fail_count = 0
    else:
        print(f"Found {len(pdf_files)} PDF(s) to process.\n")

        outcomes = await asyncio.gather(
            *(process_pdf(client, pdf, webhook_url) for pdf in pdf_files),
            return_exceptions=True,
        )

        results = {}
        success_count = 0
        fail_count = 0
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                print(f"  Unexpected error: {outcome}")
                fail_count += 1
            else:
                filename, result = outcome
                results[filename] = result
                if result["merchant_name"] is not None:
                    success_count += 1
                else:
                    fail_count += 1

    # Save results
    if args.init_ground_truth:
        output_path = Path("ground_truth.json")
    else:
        output_path = Path("results/extraction_output.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(results.items())), f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {output_path}")
    print(f"Summary: {success_count} succeeded, {fail_count} failed out of {len(pdf_files)} files.")

    if webhook_url:
        print(f"\nCheck {webhook_url} in your browser to see the webhook payloads.")

    if fail_count > 0 and success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
