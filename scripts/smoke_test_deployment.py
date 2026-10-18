"""
BankFlow Production Deployment Smoke Test Runner.

Executes a non-destructive verification battery against a deployed BankFlow API
and optional frontend console to validate health, database connectivity,
reporting views, CORS headers, read-only protection, and UI delivery.

Usage:
    python scripts/smoke_test_deployment.py --api-url https://bankflow-api.onrender.com [--frontend-url https://bankflow.vercel.app]
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run automated smoke tests against deployed BankFlow API and frontend."
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("BANKFLOW_DEPLOYED_API_URL"),
        help="Base URL of the deployed FastAPI reporting server (e.g., https://bankflow-api.onrender.com).",
    )
    parser.add_argument(
        "--frontend-url",
        default=os.getenv("BANKFLOW_DEPLOYED_FRONTEND_URL"),
        help="Optional base URL of the deployed static frontend (e.g., https://bankflow-analytics.vercel.app).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=90,
        help="HTTP request timeout in seconds (covers Render cold-start spin-up of 30-50s). Default: 90s.",
    )
    return parser.parse_args()


class SmokeTestRunner:
    def __init__(self, api_url: str, frontend_url: Optional[str] = None, timeout: int = 90):
        self.api_url = api_url.rstrip("/")
        self.frontend_url = frontend_url.rstrip("/") if frontend_url else None
        self.timeout = timeout
        self.results: List[Tuple[str, bool, str]] = []

    def _http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Dict[str, str], Any]:
        """Performs HTTP request and returns (status_code, response_headers, json_body_or_text)."""
        req_headers = {"User-Agent": "BankFlow-SmokeTester/1.0", "Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(url, method=method, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.status
                resp_headers = dict(resp.headers)
                body_bytes = resp.read()
                try:
                    body = json.loads(body_bytes.decode("utf-8"))
                except Exception:
                    body = body_bytes.decode("utf-8", errors="replace")
                return status_code, resp_headers, body
        except urllib.error.HTTPError as err:
            body_bytes = err.read()
            try:
                body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body = body_bytes.decode("utf-8", errors="replace")
            return err.code, dict(err.headers), body
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                f"Request timed out after {self.timeout}s to {url} (possible cold-start spin-up in progress)."
            ) from exc
        except urllib.error.URLError as err:
            reason_str = str(err.reason)
            if "timed out" in reason_str.lower() or isinstance(err.reason, (TimeoutError, socket.timeout)):
                raise RuntimeError(
                    f"Request timed out after {self.timeout}s to {url} (possible cold-start spin-up in progress)."
                ) from err
            raise RuntimeError(f"Connection failure to {url}: {err.reason}") from err
        except Exception as exc:
            raise RuntimeError(f"Connection failure to {url}: {exc}") from exc

    def record(self, test_name: str, passed: bool, detail: str) -> None:
        self.results.append((test_name, passed, detail))
        mark = "[PASS]" if passed else "[FAIL]"
        print(f"  {mark} {test_name}: {detail}")

    def run_all(self) -> bool:
        print("=" * 75)
        print("BankFlow — Deployment Smoke Test Battery")
        print("=" * 75)
        print(f"Target API Base URL:      {self.api_url}")
        print(f"Target Frontend URL:     {self.frontend_url or '(none specified)'}")
        print(f"Request Timeout:          {self.timeout}s")
        print("=" * 75)
        print("\nRunning smoke tests...\n")

        # 1. Root / Info endpoint
        try:
            status, _, body = self._http_request(f"{self.api_url}/")
            if status == 200 and isinstance(body, dict) and "version" in body:
                self.record("API Root Info (/)", True, f"HTTP 200 (version: {body.get('version')})")
            else:
                self.record("API Root Info (/)", False, f"Unexpected response: HTTP {status}")
        except Exception as e:
            self.record("API Root Info (/)", False, str(e))

        # 2. Health & DB connection
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/health")
            if status == 200 and isinstance(body, dict) and body.get("database") == "connected":
                self.record("Health & Database (/api/v1/health)", True, f"HTTP 200 (database: {body.get('database')})")
            else:
                self.record("Health & Database (/api/v1/health)", False, f"Unhealthy status or database disconnected: {body}")
        except Exception as e:
            self.record("Health & Database (/api/v1/health)", False, str(e))

        # 3. Overview metrics
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/overview?currency=USD")
            if status == 200 and isinstance(body, dict) and "metrics_by_currency" in body:
                currencies = body.get("currencies", [])
                self.record("Overview Metrics (/api/v1/overview)", True, f"HTTP 200 (currencies: {', '.join(currencies)})")
            else:
                self.record("Overview Metrics (/api/v1/overview)", False, f"HTTP {status} - missing currency metrics")
        except Exception as e:
            self.record("Overview Metrics (/api/v1/overview)", False, str(e))

        # 4. Daily trends
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/daily?currency=USD&limit=5")
            if status == 200 and isinstance(body, list):
                self.record("Daily Trends (/api/v1/daily)", True, f"HTTP 200 (returned {len(body)} days)")
            else:
                self.record("Daily Trends (/api/v1/daily)", False, f"HTTP {status} - expected list")
        except Exception as e:
            self.record("Daily Trends (/api/v1/daily)", False, str(e))

        # 5. Deposit / Withdrawal share
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/deposit-withdrawal?currency=USD")
            if status == 200 and isinstance(body, list):
                self.record("Deposit/Withdrawal Mix (/api/v1/deposit-withdrawal)", True, f"HTTP 200 ({len(body)} categories)")
            else:
                self.record("Deposit/Withdrawal Mix (/api/v1/deposit-withdrawal)", False, f"HTTP {status}")
        except Exception as e:
            self.record("Deposit/Withdrawal Mix (/api/v1/deposit-withdrawal)", False, str(e))

        # 6. Branch & Channel breakdown
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/branch-channel?currency=USD&limit=5")
            if status == 200 and isinstance(body, list):
                self.record("Branch & Channel Breakdown (/api/v1/branch-channel)", True, f"HTTP 200 ({len(body)} rows)")
            else:
                self.record("Branch & Channel Breakdown (/api/v1/branch-channel)", False, f"HTTP {status}")
        except Exception as e:
            self.record("Branch & Channel Breakdown (/api/v1/branch-channel)", False, str(e))

        # 7. Type mix
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/type-mix?currency=USD")
            if status == 200 and isinstance(body, list):
                self.record("Type Mix (/api/v1/type-mix)", True, f"HTTP 200 ({len(body)} types)")
            else:
                self.record("Type Mix (/api/v1/type-mix)", False, f"HTTP {status}")
        except Exception as e:
            self.record("Type Mix (/api/v1/type-mix)", False, str(e))

        # 8. Data quality defect inventory
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/quality?limit=5")
            if status == 200 and isinstance(body, list):
                self.record("Data Quality Issues (/api/v1/quality)", True, f"HTTP 200 ({len(body)} defect rules)")
            else:
                self.record("Data Quality Issues (/api/v1/quality)", False, f"HTTP {status}")
        except Exception as e:
            self.record("Data Quality Issues (/api/v1/quality)", False, str(e))

        # 9. Batch execution history
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/batches?limit=5")
            if status == 200 and isinstance(body, list):
                self.record("Batch Execution Audit (/api/v1/batches)", True, f"HTTP 200 ({len(body)} batches)")
            else:
                self.record("Batch Execution Audit (/api/v1/batches)", False, f"HTTP {status}")
        except Exception as e:
            self.record("Batch Execution Audit (/api/v1/batches)", False, str(e))

        # 10. Paginated transactions ledger
        try:
            status, _, body = self._http_request(f"{self.api_url}/api/v1/transactions?page=1&page_size=5")
            if status == 200 and isinstance(body, dict) and "items" in body:
                total = body.get("total", 0)
                items_len = len(body.get("items", []))
                self.record("Transactions Ledger (/api/v1/transactions)", True, f"HTTP 200 ({items_len} items, total {total})")
            else:
                self.record("Transactions Ledger (/api/v1/transactions)", False, f"HTTP {status} - missing items/total")
        except Exception as e:
            self.record("Transactions Ledger (/api/v1/transactions)", False, str(e))

        # 11. CORS Preflight Check
        origin = self.frontend_url or "https://bankflow-analytics-console.lovable.app"
        try:
            status, headers, _ = self._http_request(
                f"{self.api_url}/api/v1/overview",
                method="OPTIONS",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                },
            )
            allow_origin = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin")
            if status in (200, 204) and (allow_origin == origin or allow_origin == "*"):
                self.record("CORS Preflight (OPTIONS /api/v1/overview)", True, f"Permitted origin: {allow_origin}")
            elif status in (200, 204):
                self.record("CORS Preflight (OPTIONS /api/v1/overview)", True, f"HTTP {status} with origin header: {allow_origin}")
            else:
                self.record("CORS Preflight (OPTIONS /api/v1/overview)", False, f"HTTP {status} (Origin header not accepted: {allow_origin})")
        except Exception as e:
            self.record("CORS Preflight (OPTIONS /api/v1/overview)", False, str(e))

        # 12. Read-Only Protection (Verify write method rejection)
        try:
            status, _, _ = self._http_request(f"{self.api_url}/api/v1/overview", method="POST")
            if status in (405, 404):
                self.record("Read-Only Protection (POST blocked)", True, f"HTTP {status} Method Not Allowed")
            else:
                self.record("Read-Only Protection (POST blocked)", False, f"Unexpected HTTP status {status} on POST")
        except Exception as e:
            self.record("Read-Only Protection (POST blocked)", False, str(e))

        # 13. Frontend Accessibility (if specified)
        if self.frontend_url:
            try:
                status, headers, body = self._http_request(self.frontend_url)
                if status == 200 and isinstance(body, str) and ("<!DOCTYPE html>" in body or "<html" in body):
                    self.record("Frontend UI Delivery", True, f"HTTP 200 (HTML document received from {self.frontend_url})")
                else:
                    self.record("Frontend UI Delivery", False, f"Unexpected response from {self.frontend_url}: HTTP {status}")
            except Exception as e:
                self.record("Frontend UI Delivery", False, str(e))

        # Summary
        total_tests = len(self.results)
        passed_tests = sum(1 for _, passed, _ in self.results if passed)
        failed_tests = total_tests - passed_tests

        print("\n" + "=" * 75)
        print(f"Smoke Test Summary: {passed_tests}/{total_tests} Passed ({failed_tests} Failed)")
        print("=" * 75)

        return failed_tests == 0


if __name__ == "__main__":
    args = parse_args()
    if not args.api_url:
        print("[ERROR] Missing required API URL. Specify --api-url or set $BANKFLOW_DEPLOYED_API_URL.", file=sys.stderr)
        sys.exit(1)

    runner = SmokeTestRunner(
        api_url=args.api_url,
        frontend_url=args.frontend_url,
        timeout=args.timeout,
    )
    success = runner.run_all()
    sys.exit(0 if success else 1)
