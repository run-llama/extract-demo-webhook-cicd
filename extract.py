"""Extract structured data from receipt PDFs using LlamaExtract."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from llama_cloud import LlamaCloud

from schema import InvoiceSchema


def main():
    """Run extraction on all PDFs in data/ directory."""
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

    client = LlamaCloud(token=api_key)

    data_dir = Path("data")
    pdf_files = sorted(data_dir.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in data/ directory.")
        results = {}
    else:
        print(f"Found {len(pdf_files)} PDF(s) to process.\n")
        results = {}
        success_count = 0
        fail_count = 0

        for pdf_path in pdf_files:
            filename = pdf_path.name
            print(f"Processing {filename}...")

            # Upload file
            print(f"  Uploading {filename}...")
            with open(pdf_path, "rb") as f:
                file_obj = client.files.create(file=f, purpose="extract")
            print(f"  Uploaded. File ID: {file_obj.id}")

            # Build extraction kwargs
            extract_kwargs = dict(
                file_input=file_obj.id,
                configuration={
                    "data_schema": InvoiceSchema.model_json_schema(),
                    "extraction_target": "per_doc",
                    "tier": "agentic",
                },
            )

            # Add webhook if configured
            if webhook_url:
                extract_kwargs["webhook_configurations"] = [
                    {
                        "webhook_url": webhook_url,
                        "webhook_events": ["extract.success", "extract.error"],
                        "webhook_output_format": "json",
                    }
                ]
                print(f"  Webhook configured: events will be sent to {webhook_url}")

            # Create extraction job
            print(f"  Starting extraction...")
            job = client.extract.create(**extract_kwargs)

            # Poll for completion
            start_time = time.time()
            while job.status not in ("COMPLETED", "FAILED", "CANCELLED"):
                time.sleep(2)
                job = client.extract.get(job.id)

            elapsed = time.time() - start_time

            if job.status == "COMPLETED":
                result_data = job.extract_result
                if isinstance(result_data, list) and len(result_data) > 0:
                    result_data = result_data[0]
                if hasattr(result_data, "dict"):
                    result_data = result_data.dict()
                elif hasattr(result_data, "model_dump"):
                    result_data = result_data.model_dump()
                elif isinstance(result_data, dict):
                    pass
                else:
                    result_data = {"merchant_name": None, "date": None, "total": None}

                results[filename] = {
                    "merchant_name": result_data.get("merchant_name"),
                    "date": result_data.get("date"),
                    "total": result_data.get("total"),
                }
                success_count += 1
                print(f"  Completed in {elapsed:.1f}s: {results[filename]}")
            else:
                print(f"  Error: extraction {job.status} for {filename} after {elapsed:.1f}s")
                results[filename] = {"merchant_name": None, "date": None, "total": None}
                fail_count += 1

            print()

    # Save results
    if args.init_ground_truth:
        output_path = Path("ground_truth.json")
    else:
        output_path = Path("results/extraction_output.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Results saved to {output_path}")
    print(f"Summary: {success_count} succeeded, {fail_count} failed out of {len(pdf_files)} files.")

    if webhook_url:
        print(f"\nCheck {webhook_url} in your browser to see the webhook payloads.")

    if fail_count > 0 and success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
