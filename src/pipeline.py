"""CLI entrypoint for the rebuilt supervisor-centric pipeline."""
from __future__ import annotations

from src.pipeline_runner import run_pipeline


def main() -> None:
    company_name = input("Company Name: ").strip()
    web_domain = input("Web Domain: ").strip()
    if not company_name or not web_domain:
        print("Error: Company name and web domain are required.")
        return
    result = run_pipeline(company_name=company_name, web_domain=web_domain)
    print(f"Run: {result['run_id']}")
    print(f"Artifacts: {result['run_dir']}")
    print(f"Status: {result['status']}")


if __name__ == "__main__":
    main()
