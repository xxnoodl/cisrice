from collections.abc import Callable


def check_dependencies(checks: dict[str, Callable[[], object]]) -> dict[str, str]:
    results = {}
    for name, check in checks.items():
        try:
            result = check()
            results[name] = "ok" if result is not False else "unavailable"
        except Exception:
            # Never return connection strings, credentials, or raw dependency exceptions.
            results[name] = "unavailable"
    return results
