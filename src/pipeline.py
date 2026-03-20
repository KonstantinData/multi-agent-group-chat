"""Liquisto Market Intelligence Pipeline – AutoGen Group Chat."""
from __future__ import annotations

from src.pipeline_runner import run_pipeline


def main() -> None:
    company_name = input("Company Name: ").strip()
    web_domain = input("Web Domain: ").strip()

    if not company_name or not web_domain:
        print("Error: Company name and web domain are required.")
        return

    result = run_pipeline(company_name=company_name, web_domain=web_domain)
    print(f"\nResults exported to: {result['run_dir']}")
    validation_errors = result["pipeline_data"].get("validation_errors", [])
    if validation_errors:
        print("Validation warnings:")
        for item in validation_errors:
            print(f" - {item['agent']} / {item['section']}: {item['details']}")


if __name__ == "__main__":
    main()
