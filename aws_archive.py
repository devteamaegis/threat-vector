"""
AWS S3 integration — archive every transcript and threat report as immutable records.
Demonstrates production-readiness: every call has a permanent audit trail.
Bucket layout: s3://{bucket}/transcripts/{call_id}.txt
               s3://{bucket}/reports/{call_id}.json
"""
import os
import json
from datetime import datetime


def _s3_client():
    try:
        import boto3
        region = os.getenv("AWS_REGION", "us-east-1")
        return boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    except ImportError:
        return None


def archive_transcript(call_id: str, transcript: str, classification: dict) -> str | None:
    """
    Upload transcript + structured report to S3.
    Returns the S3 URI if successful, None if skipped/failed.
    """
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket or bucket == "FILL_IN":
        print(f"[{call_id}] WARNING: AWS_S3_BUCKET not set — skipping S3 archive")
        return None

    s3 = _s3_client()
    if s3 is None:
        print(f"[{call_id}] WARNING: boto3 not installed — skipping S3 archive")
        return None

    timestamp = datetime.utcnow().isoformat()
    school = classification.get("school_name", "unknown")
    level = classification.get("threat_level", 0)

    # Upload raw transcript
    transcript_key = f"transcripts/{call_id}.txt"
    report_key = f"reports/{call_id}.json"

    report = {
        "call_id": call_id,
        "timestamp": timestamp,
        "school": school,
        "threat_level": level,
        "classification": classification,
        "transcript": transcript,
    }

    try:
        s3.put_object(
            Bucket=bucket,
            Key=transcript_key,
            Body=transcript.encode("utf-8"),
            ContentType="text/plain",
            Metadata={"call_id": call_id, "school": school, "level": str(level)},
        )
        s3.put_object(
            Bucket=bucket,
            Key=report_key,
            Body=json.dumps(report, indent=2).encode("utf-8"),
            ContentType="application/json",
            Metadata={"call_id": call_id, "school": school, "level": str(level)},
        )
        uri = f"s3://{bucket}/{report_key}"
        print(f"[{call_id}] AWS S3: archived → {uri}")
        return uri
    except Exception as e:
        print(f"[{call_id}] WARNING: S3 archive failed: {e}")
        return None
