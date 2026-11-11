#!/usr/bin/env python3
# scripts/healthcheck.py
#
# Post-deploy smoke test — simulates what a real health check would do after
# deploying to staging or production.  In a real pipeline this would hit an
# HTTP endpoint; here it imports the app directly and validates the payload.
#
# Exit code 0 = healthy (pipeline step succeeds)
# Exit code 1 = unhealthy (pipeline step fails, deployment is marked failed)

import os
import sys

# Allow running from the repo root: `python scripts/healthcheck.py`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.calc import health  # noqa: E402


def run_healthcheck() -> bool:
    print("Running post-deploy health check...")
    result = health()
    print(f"  health() returned: {result}")

    checks = [
        ("status == ok",   result.get("status") == "ok"),
        ("version present", "version" in result),
    ]

    all_passed = True
    for name, passed in checks:
        icon = "✓" if passed else "✗"
        print(f"  {icon}  {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("Health check PASSED — deployment verified.")
    else:
        print("Health check FAILED — deployment is unhealthy!")

    return all_passed


if __name__ == "__main__":
    success = run_healthcheck()
    sys.exit(0 if success else 1)
