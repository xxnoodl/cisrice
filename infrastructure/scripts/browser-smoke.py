"""Verify built dashboard mounts in an installed Chromium browser (no package downloads).

Usage: python infrastructure/scripts/browser-smoke.py /path/to/chromium
Start the API and serve frontend/dist on localhost:4173 before running.
This is a limited rendering smoke check, not the future Playwright workflow suite.
"""

import subprocess
import sys
import tempfile


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cisrice-browser-") as profile:
        for route in ("/", "/operations"):
            result = subprocess.run(
                [
                    sys.argv[1],
                    "--headless",
                    "--disable-gpu",
                    "--no-first-run",
                    f"--user-data-dir={profile}",
                    "--virtual-time-budget=15000",
                    "--dump-dom",
                    f"http://127.0.0.1:4173{route}",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            assert 'id="health-title"' in result.stdout, "React health panel did not mount"
            assert 'aria-label="Main navigation"' in result.stdout, "Navigation missing"
            print(f"PASS browser rendered {route}")


if __name__ == "__main__":
    main()
