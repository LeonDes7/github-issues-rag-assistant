"""Ingest raw closed GitHub issues and comments into an S3 Bronze prefix."""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from requests import Response, Session


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = "https://api.github.com"
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 5
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def retry_delay(response: Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    return max(
                        0.0,
                        (retry_at - datetime.now(timezone.utc)).total_seconds(),
                    )
                except (TypeError, ValueError, OverflowError):
                    pass

        if response.status_code == 403 and response.headers.get(
            "X-RateLimit-Remaining"
        ) == "0":
            reset = response.headers.get("X-RateLimit-Reset")
            if reset:
                try:
                    return max(0.0, float(reset) - time.time()) + 1.0
                except ValueError:
                    pass

        if response.status_code == 403:
            try:
                message = response.json().get("message", "").lower()
            except (ValueError, AttributeError):
                message = ""
            if "rate limit" in message:
                return 60.0

    return min(60.0, 2.0**attempt)


def is_rate_limited(response: Response) -> bool:
    if response.status_code != 403:
        return False
    if response.headers.get("X-RateLimit-Remaining") == "0":
        return True
    try:
        message = response.json().get("message", "").lower()
    except (ValueError, AttributeError):
        return False
    return "rate limit" in message


def get_json(
    session: Session,
    url: str,
    params: dict[str, Any] | None = None,
) -> tuple[Any, str | None]:
    for attempt in range(MAX_RETRIES + 1):
        response: Response | None = None
        try:
            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(retry_delay(None, attempt))
            continue

        if (
            response.status_code in RETRYABLE_STATUS_CODES
            or is_rate_limited(response)
        ):
            if attempt == MAX_RETRIES:
                response.raise_for_status()
            time.sleep(retry_delay(response, attempt))
            continue

        response.raise_for_status()
        next_link = response.links.get("next", {}).get("url")
        return response.json(), next_link

    raise RuntimeError("GitHub request retries were exhausted")


def verify_github_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "api.github.com":
        raise ValueError("Refusing to send GitHub credentials to an untrusted URL")


def iter_closed_issues(
    session: Session,
    repository: str,
    counts: dict[str, int],
    target_records: int | None = None,
    max_entries_to_scan: int | None = None,
    issue_exists: Any | None = None,
    since: str | None = None,
):
    issue_url = f"{API_ROOT}/repos/{repository}/issues"
    verify_github_url(issue_url)
    params: dict[str, Any] | None = {
        "state": "closed",
        "per_page": 100,
        "page": 1,
    }
    if since:
        params["since"] = since
    while (
        issue_url
        and (
            max_entries_to_scan is None
            or counts["issues_seen"] < max_entries_to_scan
        )
        and (
            target_records is None
            or counts["records_uploaded"] + counts["resumed_issues"]
            < target_records
        )
    ):
        verify_github_url(issue_url)
        page, next_url = get_json(session, issue_url, params=params)
        params = None
        if not isinstance(page, list):
            raise ValueError("GitHub issues endpoint returned a non-list response")

        for issue in page:
            if (
                (
                    max_entries_to_scan is not None
                    and counts["issues_seen"] >= max_entries_to_scan
                )
                or (
                    target_records is not None
                    and counts["records_uploaded"] + counts["resumed_issues"]
                    >= target_records
                )
            ):
                break
            counts["issues_seen"] += 1

            if "pull_request" in issue:
                counts["pull_requests_skipped"] += 1
                continue

            issue_number = issue.get("number")
            if isinstance(issue_number, bool) or not isinstance(issue_number, int):
                raise ValueError("GitHub issue response has an invalid issue number")
            updated_at = issue.get("updated_at")
            if isinstance(updated_at, str):
                current_max = counts["max_updated_at"]
                if current_max is None or updated_at > current_max:
                    counts["max_updated_at"] = updated_at
            if issue_exists is not None and issue_exists(issue_number):
                counts["resumed_issues"] += 1
                continue

            comments_url = issue.get("comments_url")
            if not isinstance(comments_url, str):
                raise ValueError(
                    f"Issue {issue.get('number', '<unknown>')} has no comments URL"
                )
            verify_github_url(comments_url)
            comments: list[dict[str, Any]] = []
            comments_next: str | None = comments_url
            comments_params: dict[str, Any] | None = {"per_page": 100, "page": 1}

            while comments_next:
                verify_github_url(comments_next)
                comment_page, comments_next = get_json(
                    session,
                    comments_next,
                    params=comments_params,
                )
                comments_params = None
                if not isinstance(comment_page, list):
                    raise ValueError(
                        f"Comments endpoint for issue {issue.get('number')} "
                        "returned a non-list response"
                    )
                comments.extend(comment_page)

            counts["comments_uploaded"] += len(comments)
            counts["records_uploaded"] += 1
            yield {"issue": issue, "comments": comments}

        issue_url = next_url


def collect_closed_issues(
    session: Session,
    repository: str,
    target_records: int | None = None,
    max_entries_to_scan: int | None = None,
    issue_exists: Any | None = None,
    since: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    counts = {
        "issues_seen": 0,
        "pull_requests_skipped": 0,
        "resumed_issues": 0,
        "records_uploaded": 0,
        "comments_uploaded": 0,
        "max_updated_at": None,
    }
    records = list(
        iter_closed_issues(
            session,
            repository,
            counts,
            target_records=target_records,
            max_entries_to_scan=max_entries_to_scan,
            issue_exists=issue_exists,
            since=since,
        )
    )
    return records, counts


def required_environment() -> dict[str, Any]:
    load_dotenv(PROJECT_ROOT / ".env")
    required_names = ("GITHUB_TOKEN", "AWS_DEFAULT_REGION", "S3_BUCKET")
    credential_names = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION")
    if aws_region:
        os.environ.setdefault("AWS_DEFAULT_REGION", aws_region)
    missing = [name for name in required_names if not os.getenv(name)]
    if bool(os.getenv(credential_names[0])) != bool(os.getenv(credential_names[1])):
        raise ValueError(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set together"
        )
    if missing:
        raise ValueError(f"Missing required .env settings: {', '.join(missing)}")
    repositories = [
        repository.strip()
        for repository in os.getenv(
            "GITHUB_REPOS",
            "tiangolo/fastapi,encode/starlette,pydantic/pydantic",
        ).split(",")
        if repository.strip()
    ]
    try:
        target_records = (
            int(os.environ["TARGET_RECORDS_PER_REPO"])
            if os.getenv("TARGET_RECORDS_PER_REPO")
            else None
        )
        max_entries = (
            int(os.environ["MAX_ENTRIES_TO_SCAN_PER_REPO"])
            if os.getenv("MAX_ENTRIES_TO_SCAN_PER_REPO")
            else None
        )
    except ValueError as exc:
        raise ValueError(
            "TARGET_RECORDS_PER_REPO and MAX_ENTRIES_TO_SCAN_PER_REPO "
            "must be integers"
        ) from exc
    if not repositories:
        raise ValueError("GITHUB_REPOS must contain at least one repository")
    from rag_assistant.repository_scope import configured_repositories
    repositories = configured_repositories()
    if (target_records is not None and target_records < 1) or (
        max_entries is not None and max_entries < 1
    ):
        raise ValueError("Repository target and scan limit must be positive")
    return {
        **{name: os.environ[name] for name in required_names},
        **{name: os.getenv(name) for name in credential_names},
        "GITHUB_REPOS": repositories,
        "TARGET_RECORDS_PER_REPO": target_records,
        "MAX_ENTRIES_TO_SCAN_PER_REPO": max_entries,
    }


def s3_client(settings: dict[str, str]):
    session_token = os.getenv("AWS_SESSION_TOKEN")
    client_options: dict[str, str] = {
        "region_name": settings["AWS_DEFAULT_REGION"],
    }
    if settings.get("AWS_ACCESS_KEY_ID") and settings.get("AWS_SECRET_ACCESS_KEY"):
        client_options["aws_access_key_id"] = settings["AWS_ACCESS_KEY_ID"]
        client_options["aws_secret_access_key"] = settings["AWS_SECRET_ACCESS_KEY"]
    if session_token and "aws_access_key_id" in client_options:
        client_options["aws_session_token"] = session_token
    return boto3.client("s3", **client_options)


def ingest_repository(
    repository: str,
    target_records: int | None,
    max_entries_to_scan: int | None,
    settings: dict[str, Any],
    client: Any,
    since: str | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError(f"Invalid repository name: {repository!r}")

    github_session = requests.Session()
    github_session.headers.update(
        {
            **GITHUB_HEADERS,
            "Authorization": f"Bearer {settings['GITHUB_TOKEN']}",
            "User-Agent": "trustworthy-rag-assistant",
        }
    )
    ingested_at = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_repository = re.sub(r"[^A-Za-z0-9_.-]", "__", repository)
    prefix = f"bronze/github/repo={safe_repository}"
    counts = {
        "issues_seen": 0,
        "pull_requests_skipped": 0,
        "resumed_issues": 0,
        "records_uploaded": 0,
        "comments_uploaded": 0,
        "max_updated_at": None,
        "max_updated_at": None,
    }

    def object_exists(issue_number: int) -> bool:
        try:
            client.head_object(
                Bucket=settings["S3_BUCKET"],
                Key=f"{prefix}/issue={issue_number}.json",
            )
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    issues_key = f"{prefix}/issue=<issue_number>.json"
    try:
        records = iter_closed_issues(
            github_session,
            repository,
            counts,
            target_records=target_records,
            max_entries_to_scan=max_entries_to_scan,
            issue_exists=object_exists if since is None else None,
            since=since,
        )
        for record in records:
            issue_number = record["issue"]["number"]
            client.put_object(
                Bucket=settings["S3_BUCKET"],
                Key=f"{prefix}/issue={issue_number}.json",
                Body=json.dumps(
                    record,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
                ContentType="application/json",
            )
    finally:
        github_session.close()

    manifest_key = f"{prefix}/runs/{ingested_at}/manifest.json"
    manifest = {
        "repository": repository,
        "ingested_at": ingested_at,
        "target_records_per_repo": target_records,
        "max_entries_to_scan_per_repo": max_entries_to_scan,
        "since": since,
        **counts,
    }
    client.put_object(
        Bucket=settings["S3_BUCKET"],
        Key=manifest_key,
        Body=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return {
        "bucket": settings["S3_BUCKET"],
        "issues_key": issues_key,
        "manifest_key": manifest_key,
        **manifest,
    }


def run_ingestion(
    repositories: list[str],
    target_records: int | None = None,
    max_entries_to_scan: int | None = None,
    since_by_repository: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    from rag_assistant.repository_scope import selected_repositories

    repositories = selected_repositories(repositories)
    settings = required_environment()
    client = s3_client(settings)
    results = [
        ingest_repository(
            repository,
            target_records,
            max_entries_to_scan,
            settings,
            client,
            since=(since_by_repository or {}).get(repository),
        )
        for repository in repositories
    ]
    totals = {
        key: sum(result[key] for result in results)
        for key in (
            "issues_seen",
            "pull_requests_skipped",
            "resumed_issues",
            "records_uploaded",
            "comments_uploaded",
        )
    }
    return {
        "repositories": results,
        "totals": totals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest raw closed GitHub issues and comments to S3 Bronze."
    )
    parser.add_argument(
        "--repos",
        help="Comma-separated repositories (defaults to GITHUB_REPOS in .env)",
    )
    parser.add_argument(
        "--target-records-per-repo",
        type=int,
        help="Optional upper bound on new or resumed issue records per repository",
    )
    parser.add_argument(
        "--max-entries-to-scan-per-repo",
        type=int,
        help="Optional upper bound on GitHub issue entries to inspect per repository",
    )
    args = parser.parse_args()

    try:
        settings = required_environment()
        repositories = (
            [repository.strip() for repository in args.repos.split(",")]
            if args.repos
            else settings["GITHUB_REPOS"]
        )
        target_records = (
            args.target_records_per_repo
            if args.target_records_per_repo is not None
            else settings["TARGET_RECORDS_PER_REPO"]
        )
        max_entries = (
            args.max_entries_to_scan_per_repo
            if args.max_entries_to_scan_per_repo is not None
            else settings["MAX_ENTRIES_TO_SCAN_PER_REPO"]
        )
        if not repositories or any(not repository for repository in repositories):
            parser.error("At least one non-empty repository is required")
        if (target_records is not None and target_records < 1) or (
            max_entries is not None and max_entries < 1
        ):
            parser.error("Record target and scan limit must be positive integers")
        for repository in repositories:
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
                parser.error(f"Invalid repository name: {repository!r}")
        result = run_ingestion(repositories, target_records, max_entries)
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        raise SystemExit(f"Ingestion failed: {exc}") from exc

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
