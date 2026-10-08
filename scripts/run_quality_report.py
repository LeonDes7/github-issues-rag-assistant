"""Run existing quality checks with bounded, read-only S3 prefetching."""

import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from rag_assistant import data_quality, load_bronze_to_rds


class PrefetchS3:
    def __init__(self, client, pool):
        self.client, self.pool = client, pool
        self.cached = {}

    def _read(self, bucket_key):
        bucket, key = bucket_key
        result = self.client.get_object(Bucket=bucket, Key=key)
        try:
            return key, result["Body"].read()
        finally:
            result["Body"].close()

    def list_objects_v2(self, **kwargs):
        page = self.client.list_objects_v2(**kwargs)
        keys = [item["Key"] for item in page.get("Contents", []) if item["Key"].endswith(".json")]
        self.cached.update(self.pool.map(self._read, [(kwargs["Bucket"], key) for key in keys]))
        print(f"Prefetched {len(keys)} objects under {kwargs['Prefix']}", flush=True)
        return page

    def get_object(self, **kwargs):
        key = kwargs["Key"]
        if key in self.cached:
            return {"Body": io.BytesIO(self.cached.pop(key))}
        return self.client.get_object(**kwargs)


def main():
    settings = load_bronze_to_rds.required_environment()
    client = load_bronze_to_rds.create_s3_client(settings)
    with ThreadPoolExecutor(max_workers=8) as pool:
        prefetch = PrefetchS3(client, pool)
        # Existing normalization, dedupe, and all three layer checks are unchanged.
        with patch.object(load_bronze_to_rds, "create_s3_client", return_value=prefetch):
            report = data_quality.run_quality_checks()
    report["read_method"] = "Existing quality checks, eight-worker read-only S3 prefetch; unchanged validation and source order"
    path = Path(__file__).resolve().parents[1] / "docs/corpus/data_quality_scoped_report.json"
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
