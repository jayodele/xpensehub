"""
Job Application Agent — Senior Product Management roles in London.

Usage:
    python -m job_agent.agent                    # run full search + apply loop
    python -m job_agent.agent --list             # list saved applications
    python -m job_agent.agent --max-jobs 5       # limit to 5 applications
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic

from .cv_profile import CV_TEXT, PROFILE
from .tools import TOOL_SCHEMAS, build_cover_letter_prompt, dispatch, list_applications

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = f"""You are a job application agent acting on behalf of Jerry Ayodele, a Senior Product Leader based in London.

Your job:
1. Search Reed.co.uk for Senior Product Manager and Senior Product Lead roles in London (try at least 2 search queries for variety).
2. For each promising role, fetch the full job description.
3. Write a tailored, compelling cover letter using Jerry's CV and the specific job requirements.
4. Save each application using the save_application tool.
5. After processing all jobs, give a concise summary of what was done.

Jerry's CV:
{CV_TEXT}

Guidelines:
- Target roles with titles like: Senior Product Manager, Senior Product Lead, Head of Product, Principal Product Manager, Group Product Manager.
- Prefer roles in fintech, enterprise software, AI/ML products, consumer apps — areas where Jerry has proven experience.
- Skip roles that are clearly junior or unrelated (e.g. physical product, manufacturing).
- Cover letters should be 3-4 paragraphs, specific to each company, confident and professional.
- Always save every application you prepare.
"""


def run_agent(max_jobs: int = 8) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Please find and apply to up to {max_jobs} Senior Product Management roles in London "
                "on Reed.co.uk. For each role, write a tailored cover letter and save the application. "
                "Start by searching for relevant jobs, then process each one."
            ),
        }
    ]

    print(f"\n{'='*60}")
    print(f"  Job Application Agent — {PROFILE['name']}")
    print(f"  Target: Senior PM roles in London")
    print(f"  Max applications: {max_jobs}")
    print(f"{'='*60}\n")

    turn = 0
    while True:
        turn += 1
        print(f"[Turn {turn}] Calling Claude...", flush=True)

        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Append assistant response
        messages.append({"role": "assistant", "content": response.content})

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type == "text":
                print(f"\n[Agent] {block.text}\n")
            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                print(f"  -> Tool: {tool_name}({json.dumps(tool_input)[:120]}...)" if len(json.dumps(tool_input)) > 120 else f"  -> Tool: {tool_name}({json.dumps(tool_input)})")

                try:
                    result = dispatch(tool_name, tool_input)
                except Exception as exc:
                    result = {"error": str(exc)}

                # Pretty-print key results
                if tool_name == "search_jobs" and isinstance(result, list):
                    print(f"     Found {len(result)} jobs")
                    for j in result:
                        if "error" not in j:
                            print(f"       • {j.get('title')} @ {j.get('company')} — {j.get('salary')}")
                elif tool_name == "save_application" and isinstance(result, dict):
                    print(f"     Saved: {result.get('job_title')} @ {result.get('company')}")
                elif tool_name == "get_job_details" and isinstance(result, dict):
                    print(f"     Details: {result.get('title')} @ {result.get('company')}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Check stop condition
        if response.stop_reason == "end_turn":
            break
        if response.stop_reason not in ("tool_use",):
            print(f"[Agent stopped: {response.stop_reason}]")
            break

    # Final summary
    apps = list_applications()
    print(f"\n{'='*60}")
    print(f"  Applications saved: {len(apps)}")
    for a in apps:
        print(f"  • {a['job_title']} @ {a['company']} — {a['status']}")
    print(f"\n  Tracker: {Path(__file__).parent / 'applications.json'}")
    print(f"{'='*60}\n")


def print_applications() -> None:
    apps = list_applications()
    if not apps:
        print("No applications saved yet. Run the agent first.")
        return
    for i, a in enumerate(apps, 1):
        print(f"\n{'─'*60}")
        print(f"[{i}] {a['job_title']} @ {a['company']}")
        print(f"    Status : {a['status']}")
        print(f"    Salary : {a.get('salary', 'N/A')}")
        print(f"    URL    : {a.get('url', 'N/A')}")
        print(f"    Applied: {a.get('applied_at', 'N/A')}")
        print(f"\n--- Cover Letter ---\n{a['cover_letter'][:600]}...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Senior PM Job Application Agent")
    parser.add_argument("--list", action="store_true", help="List saved applications")
    parser.add_argument("--max-jobs", type=int, default=8, help="Max applications to prepare")
    args = parser.parse_args()

    if args.list:
        print_applications()
    else:
        run_agent(max_jobs=args.max_jobs)


if __name__ == "__main__":
    main()
