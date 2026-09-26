#!/usr/bin/env python3
"""
CLI Runner for Offline Personal Fitness Concierge (Gemma 4 Edge Agent).
Allows running interactive REPL or automated scenario demonstrations.
"""

import argparse
import json
import sys
from concierge.engine import SDACEngine
from concierge.models import NetworkStatus, DeviceMemoryHeadroom, Telemetry
from database.db_manager import DBManager

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


PRESET_SCENARIOS = {
    "knee": (
        "I am an adult with bad knee pain and patellar tendonitis. Recommend a 15 min safe workout routine.",
        "OFFLINE"
    ),
    "senior": (
        "I am a 72-year-old senior. Give me a high-intensity anaerobic HIIT circuit workout.",
        "OFFLINE"
    ),
    "chest_pain": (
        "I was about to workout but I suddenly have sharp radiating chest pain and dizziness.",
        "OFFLINE"
    ),
    "live_offline": (
        "Check my squat form live using the camera and coach my depth in real time.",
        "OFFLINE"
    ),
    "live_online": (
        "Check my squat form live using the camera and coach my depth in real time.",
        "ONLINE"
    ),
    "decompression": (
        "Can you give me an offline guide and stretching protocol for lower back decompression?",
        "OFFLINE"
    )
}


def print_sdac_banner():
    print(f"""{CYAN}{BOLD}
╔════════════════════════════════════════════════════════════════════════════╗
║   GEMMA 4 EDGE AGENT: OFFLINE PERSONAL FITNESS CONCIERGE & ROUTER          ║
║   Architecture: Sense -> Decide -> Act -> Check (SDAC) | 100% On-Device   ║
╚════════════════════════════════════════════════════════════════════════════╝{RESET}
""")


def display_turn_output(output, raw_json=False):
    if raw_json:
        print(json.dumps(output.model_dump(), indent=2))
        return

    tp = output.thought_process
    sd = tp.sensed_demographics
    act = output.action
    lsu = output.local_state_update
    ur = output.user_response

    print(f"\n{MAGENTA}{BOLD}─── STEP 1: SENSE (Input Ingestion & Telemetry) ──────────────────────────{RESET}")
    print(f"  • Demographic Profile: {BOLD}Age={sd.age_band.upper()}{RESET} | {BOLD}Tier={sd.fitness_tier.upper()}{RESET} | {BOLD}Target={sd.target_duration_min}m{RESET}")
    print(f"  • Orthopedic Flags:    {YELLOW}{sd.orthopedic_flags or 'None logged'}{RESET}")
    print(f"  • Available Equipment: {sd.available_equipment}")

    print(f"\n{CYAN}{BOLD}─── STEP 2: DECIDE (Strategy & Routing Classification) ───────────────────{RESET}")
    print(f"  • Routing Branch:      {BOLD}{tp.routing_decision}{RESET}")
    print(f"  • Strategy Notes:      {tp.audit_notes or 'Safe local edge routing tree.'}")

    print(f"\n{YELLOW}{BOLD}─── STEP 3: ACT (Local SQLite Function Call) ─────────────────────────────{RESET}")
    print(f"  • Executed Tool:       {BOLD}{act.tool_call}(){RESET}")
    print(f"  • Parameters:          {json.dumps(act.parameters)}")

    print(f"\n{GREEN}{BOLD}─── STEP 4: CHECK (Deterministic Safety Audit & Recovery) ────────────────{RESET}")
    audit_color = GREEN if tp.safety_audit_passed else RED
    print(f"  • Audit Status:        {audit_color}{BOLD}{'PASSED' if tp.safety_audit_passed else 'FAILED'}{RESET}")
    print(f"  • Recovery Attempts:   {tp.recovery_attempts} / 2 (Budget max 2)")
    print(f"  • Committed State:     {BOLD}{lsu.session_status}{RESET}")

    print(f"\n{BOLD}─── USER RESPONSE ────────────────────────────────────────────────────────{RESET}")
    print(ur.message)

    if ur.attached_resources:
        print(f"\n{CYAN}Attached Offline Resources:{RESET}")
        for r in ur.attached_resources:
            print(f"  📖 [{r.id}] {r.title} ({r.offline_path})")

    if ur.live_tool_cta:
        cta = ur.live_tool_cta
        status_tag = f"{GREEN}[ONLINE READY]{RESET}" if cta.available else f"{YELLOW}[OFFLINE DEFERRED]{RESET}"
        print(f"\n{status_tag} {cta.notice}")
        if cta.handoff_token:
            print(f"  Token: {CYAN}{cta.handoff_token}{RESET}")
    print(f"{BOLD}──────────────────────────────────────────────────────────────────────────{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Gemma 4 Edge Fitness Concierge CLI")
    parser.add_argument("--scenario", choices=list(PRESET_SCENARIOS.keys()), help="Run a specific test scenario")
    parser.add_argument("--network", choices=["OFFLINE", "ONLINE", "UNSTABLE"], default="OFFLINE", help="Telemetry network status")
    parser.add_argument("--json", action="store_true", help="Print strict JSON schema output")
    args = parser.parse_args()

    engine = SDACEngine()
    print_sdac_banner()

    if args.scenario:
        prompt, net_mode = PRESET_SCENARIOS[args.scenario]
        net_mode = args.network if args.network != "OFFLINE" else net_mode
        print(f"{BOLD}Running Scenario '{args.scenario}':{RESET} \"{prompt}\" (Network: {net_mode})")
        telemetry = Telemetry(network_status=NetworkStatus(net_mode))
        output = engine.run_sdac_cycle(user_input=prompt, telemetry=telemetry)
        display_turn_output(output, raw_json=args.json)
        return

    print("Type your message below. Type 'exit' or 'quit' to quit.\n")
    print(f"Current Network Status: {BOLD}{args.network}{RESET} (Use --network ONLINE to test online mode)\n")

    while True:
        try:
            user_input = input(f"{CYAN}You > {RESET}").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Exiting Gemma 4 Edge Agent.")
                sys.exit(0)

            telemetry = Telemetry(network_status=NetworkStatus(args.network))
            output = engine.run_sdac_cycle(user_input=user_input, telemetry=telemetry)
            display_turn_output(output, raw_json=args.json)

        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)


if __name__ == "__main__":
    main()
