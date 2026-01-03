import sys

import httpx

URL = "http://localhost:8000/v1/health"
# No payload needed for health endpoint
PAYLOAD = None
LIMIT = 100
TOTAL_REQUESTS = 110


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "shadow"
    print(f"Testing Rate Limit in {mode} mode...")

    success_count = 0
    blocked_count = 0

    # Use a persistent client for speed
    with httpx.Client(timeout=5.0) as client:
        for i in range(TOTAL_REQUESTS):
            try:
                # Need to spoof IP because 127.0.0.1 is whitelisted
                headers = {"X-Forwarded-For": "10.0.0.50"}
                resp = client.get(URL, headers=headers)

                if resp.status_code == 200:
                    success_count += 1
                elif resp.status_code in [500, 503, 504]:
                    # Failed in backend, but passed rate limiter
                    success_count += 1
                elif resp.status_code == 429:
                    blocked_count += 1
                    print(".", end="", flush=True) if i % 10 == 0 else None
                else:
                    print(f"Unexpected status: {resp.status_code}")
            except Exception as e:
                print(f"Error: {e}")

            if i % 10 == 0:
                print(f"Sent {i}...")

    print(f"\nResults for {mode} mode:")
    print(f"Success (200): {success_count}")
    print(f"Blocked (429): {blocked_count}")

    if mode == "shadow":
        if blocked_count > 0:
            print("FAILURE: Blocked requests in Shadow Mode!")
            sys.exit(1)
        if success_count < TOTAL_REQUESTS:
            print("FAILURE: Some requests failed unexpectedly")
            sys.exit(1)
        print("SUCCESS: Shadow Mode Verified (Traffic passed through)")

    elif mode == "active":
        if blocked_count == 0:
            print("FAILURE: No requests blocked in Active Mode!")
            sys.exit(1)
        # In strict memory limit, 101st should block.
        # But we might have sliding windows etc.
        if success_count > LIMIT + 5:  # Tolerance
            print("FAILURE: Too many requests passed in Active Mode")
            sys.exit(1)
        print("SUCCESS: Active Mode Verified (Traffic blocked)")


if __name__ == "__main__":
    main()
