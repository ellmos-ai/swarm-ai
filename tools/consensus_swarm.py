#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
consensus_swarm.py - Consensus swarm pattern with Claude API
==============================================================

Run multiple LLM instances on the same question in parallel,
then compare results and take a majority decision.

Use cases:
- Fact validation (is a statement true?)
- Classification (which category?)
- Extraction (which entities?)
- Quality control (is a summary correct?)

Usage:
    python consensus_swarm.py "What is the capital of France?"
    python consensus_swarm.py --agents 5 --question "Is Python typed?"
    python consensus_swarm.py --mode classify --categories "positive,negative,neutral" --question "The movie was okay."
    python consensus_swarm.py --dry-run --question "Test question"

Author: Lukas Geiger (ellmos-ai)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import anthropic

try:
    import anthropic  # noqa: F811
except ImportError:
    anthropic = None  # noqa: F811

# --- Constants ---

MODEL = "claude-haiku-4-5-20251001"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0
DEFAULT_AGENTS = 5
DEFAULT_WORKERS = 5
MAX_QUESTION_BYTES = 100_000
MAX_CATEGORIES = 50
MAX_CATEGORY_BYTES = 10_000

MODEL_COSTS_PER_1M = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-fable-5": {"input": 10.00, "output": 50.00},
}
COST_PER_1M = MODEL_COSTS_PER_1M[MODEL]  # Backwards-compatible default.


def resolve_model_costs(model: str, override: Optional[Dict] = None) -> Dict:
    """Return explicit per-million-token prices; never silently misprice."""
    costs = override or MODEL_COSTS_PER_1M.get(model)
    if not costs or set(costs) != {"input", "output"}:
        raise ValueError(
            f"no pricing configured for model {model!r}; provide input/output costs"
        )
    try:
        costs = {key: float(value) for key, value in costs.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError("model costs must be numeric") from exc
    if any(not math.isfinite(value) or value < 0 for value in costs.values()):
        raise ValueError("model costs must be finite and non-negative")
    return costs

# --- API Key ---


def get_api_key() -> str:
    """API-Key aus Env-Variable ANTHROPIC_API_KEY laden."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return api_key

    raise ValueError(
        "ANTHROPIC_API_KEY nicht konfiguriert!\n"
        "  export ANTHROPIC_API_KEY=sk-ant-api03-..."
    )


# --- Swarm Agents ---


def query_agent(client: anthropic.Anthropic, agent_id: int,
                system_prompt: str, user_prompt: str,
                model: str = MODEL) -> Dict:
    """
    Einzelner Agent beantwortet die Frage.

    Returns:
        Dict mit answer, agent_id, input_tokens, output_tokens, error
    """
    for attempt in range(MAX_RETRIES):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=256,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.7,  # Some variance for diversity
            )

            answer = message.content[0].text.strip()

            return {
                "agent_id": agent_id,
                "answer": answer,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
                "error": None,
            }

        except Exception as e:
            error_str = str(e)

            if "rate" in error_str.lower() or "429" in error_str:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)
                continue

            if "overloaded" in error_str.lower() or "529" in error_str:
                time.sleep(RETRY_BASE_DELAY * (attempt + 1))
                continue

            if attempt >= MAX_RETRIES - 1:
                return {
                    "agent_id": agent_id,
                    "answer": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": error_str[:200],
                }

            time.sleep(RETRY_BASE_DELAY)

    return {
        "agent_id": agent_id,
        "answer": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "error": f"Max Retries ({MAX_RETRIES}) erreicht",
    }


def build_prompts(question: str, mode: str = "answer",
                  categories: Optional[List[str]] = None) -> Tuple[str, str]:
    """
    Baut System- und User-Prompt je nach Modus.

    Returns:
        (system_prompt, user_prompt)
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if len(question.encode("utf-8")) > MAX_QUESTION_BYTES:
        raise ValueError(f"question exceeds {MAX_QUESTION_BYTES} UTF-8 bytes")
    if mode not in {"answer", "classify", "boolean"}:
        raise ValueError(f"unsupported mode: {mode}")
    if mode == "classify":
        if not categories:
            raise ValueError("classify mode requires at least one category")
        if len(categories) > MAX_CATEGORIES:
            raise ValueError(f"at most {MAX_CATEGORIES} categories are allowed")
        if any(not isinstance(category, str) or not category.strip()
               for category in categories):
            raise ValueError("categories must be non-empty strings")
        normalized_categories = [category.strip().casefold() for category in categories]
        if len(normalized_categories) != len(set(normalized_categories)):
            raise ValueError("categories must be unique (case-insensitive)")
        if sum(len(category.encode("utf-8")) for category in categories) > MAX_CATEGORY_BYTES:
            raise ValueError(f"categories exceed {MAX_CATEGORY_BYTES} UTF-8 bytes")

    if mode == "classify":
        cat_str = ", ".join(categories)
        system_prompt = (
            "Du bist ein Klassifikations-Agent. "
            f"Kategorisiere die Eingabe in GENAU EINE der folgenden Kategorien: {cat_str}\n\n"
            "REGELN:\n"
            "- Antworte NUR mit dem Kategorienamen\n"
            "- Keine Erklaerung, kein Satz, nur das eine Wort\n"
            "- Wenn keine Kategorie passt, waehle die naechstliegende"
        )
        user_prompt = question

    elif mode == "boolean":
        system_prompt = (
            "Du bist ein Fakten-Pruefungs-Agent. "
            "Beantworte die Frage mit JA oder NEIN.\n\n"
            "REGELN:\n"
            "- Antworte NUR mit 'JA' oder 'NEIN'\n"
            "- Keine Erklaerung, nur ein Wort"
        )
        user_prompt = question

    else:  # mode == "answer"
        system_prompt = (
            "Du bist ein Wissens-Agent in einem Schwarm-System. "
            "Beantworte die Frage praezise und kurz (1-2 Saetze).\n\n"
            "REGELN:\n"
            "- Kurz und praezise antworten\n"
            "- Faktenbasiert\n"
            "- Keine Einleitungen wie 'Die Antwort ist...'"
        )
        user_prompt = question

    return system_prompt, user_prompt


def compute_consensus(results: List[Dict], mode: str = "answer",
                      categories: Optional[List[str]] = None) -> Dict:
    """
    Berechnet Konsensus aus mehreren Agent-Antworten.

    Returns:
        Dict mit consensus_answer, confidence, agreement_ratio, votes
    """
    valid_answers = []
    allowed = {category.strip().upper() for category in categories or []}
    for result in results:
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            continue
        normalized = answer.strip().upper()
        if mode == "boolean" and normalized not in {"JA", "NEIN"}:
            continue
        if mode == "classify" and allowed and normalized not in allowed:
            continue
        valid_answers.append(answer)

    if not valid_answers:
        return {
            "consensus_answer": None,
            "confidence": 0.0,
            "agreement_ratio": 0.0,
            "votes": {},
            "total_agents": len(results),
            "valid_responses": 0,
            "response_rate": 0.0,
            "tie": False,
            "tied_answers": [],
        }

    # Normalisierung je nach Modus
    if mode in ("classify", "boolean"):
        # Exakter Vergleich (case-insensitive)
        normalized = [a.strip().upper() for a in valid_answers]
    else:
        # Fuer freie Antworten: lowercase, Satzzeichen entfernen
        normalized = [a.strip().lower().rstrip('.!?') for a in valid_answers]

    vote_counts = Counter(normalized)
    winner_count = max(vote_counts.values())
    winners = sorted(answer for answer, count in vote_counts.items()
                     if count == winner_count)
    tie = len(winners) > 1
    winner = winners[0] if not tie else None

    # Confidence includes failed/invalid agents. Agreement is only among valid
    # responses, so callers can distinguish certainty from response quality.
    confidence = winner_count / len(results) if results else 0.0
    agreement_ratio = winner_count / len(valid_answers)
    response_rate = len(valid_answers) / len(results) if results else 0.0

    # Originale Antwort fuer den Gewinner finden
    consensus_answer = None
    if winner is not None:
        for answer, norm in zip(valid_answers, normalized):
            if norm == winner:
                consensus_answer = answer
                break

    return {
        "consensus_answer": consensus_answer,
        "confidence": confidence,
        "agreement_ratio": agreement_ratio,
        "votes": dict(vote_counts),
        "total_agents": len(results),
        "valid_responses": len(valid_answers),
        "response_rate": response_rate,
        "tie": tie,
        "tied_answers": winners if tie else [],
    }


# --- Main Orchestration ---


def run_consensus(question: str, num_agents: int = DEFAULT_AGENTS,
                  workers: int = DEFAULT_WORKERS, mode: str = "answer",
                  categories: Optional[List[str]] = None,
                   dry_run: bool = False, model: str = MODEL,
                   quiet: bool = False,
                   cost_per_1m: Optional[Dict] = None,
                   max_budget_usd: Optional[float] = None) -> Dict:
    """
    Fuehrt Konsensus-Schwarm aus.

    Returns:
        Dict mit consensus, individual_results, stats
    """
    if not 1 <= num_agents <= 100:
        raise ValueError("num_agents must be between 1 and 100")
    if not 1 <= workers <= 100:
        raise ValueError("workers must be between 1 and 100")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must be a non-empty string")
    costs = resolve_model_costs(model, cost_per_1m)
    system_prompt, user_prompt = build_prompts(question, mode, categories)
    input_upper = num_agents * (
        len(system_prompt.encode("utf-8")) + len(user_prompt.encode("utf-8"))
    )
    output_upper = num_agents * 256
    cost_upper = MAX_RETRIES * (
        input_upper * costs["input"] + output_upper * costs["output"]
    ) / 1_000_000
    if not dry_run:
        if max_budget_usd is None or not math.isfinite(max_budget_usd) \
                or max_budget_usd <= 0:
            raise ValueError("live consensus requires a positive finite max_budget_usd")
        if cost_upper > max_budget_usd:
            raise ValueError(
                f"conservative cost bound ${cost_upper:.6f} exceeds budget "
                f"${max_budget_usd:.6f}"
            )

    def emit(message: str = "") -> None:
        if not quiet:
            print(message)

    emit(f"[KONSENSUS] Frage: {question}")
    emit(f"[KONSENSUS] Modus: {mode}")
    emit(f"[KONSENSUS] Agenten: {num_agents}, Worker: {workers}\n")

    if dry_run:
        est_input = num_agents * (len(system_prompt) + len(question)) // 4
        est_output = num_agents * 50
        est_cost = (est_input * costs["input"] + est_output * costs["output"]) / 1_000_000
        emit(f"[DRY-RUN] Geschaetzte Kosten: ${est_cost:.6f}")
        emit(f"           Input-Tokens:  ~{est_input}")
        emit(f"           Output-Tokens: ~{est_output}")
        emit(f"           API-Calls: {num_agents}")
        return {
            "dry_run": True,
            "model": model,
            "agents": num_agents,
            "estimated_input_tokens": est_input,
            "estimated_output_tokens": est_output,
            "estimated_cost_usd": est_cost,
            "conservative_cost_bound_usd": cost_upper,
        }

    if anthropic is None:
        raise RuntimeError("anthropic SDK not installed: pip install anthropic")
    api_key = get_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    # Execute in parallel
    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(query_agent, client, i, system_prompt, user_prompt, model): i
            for i in range(num_agents)
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            agent_id = result["agent_id"]

            if result["error"]:
                emit(f"  Agent {agent_id}: FEHLER - {result['error'][:80]}")
            else:
                preview = result["answer"][:80] if result["answer"] else "?"
                emit(f"  Agent {agent_id}: {preview}")

    elapsed = time.time() - start_time
    results.sort(key=lambda result: result["agent_id"])

    # Konsensus berechnen
    consensus = compute_consensus(results, mode, categories)

    # Token statistics
    total_input = sum(r["input_tokens"] for r in results)
    total_output = sum(r["output_tokens"] for r in results)
    total_cost = (total_input * costs["input"] + total_output * costs["output"]) / 1_000_000

    # Output
    emit(f"\n{'=' * 60}")
    emit("  KONSENSUS-ERGEBNIS")
    emit(f"{'=' * 60}")
    emit(f"  Antwort:         {consensus['consensus_answer']}")
    emit(f"  Confidence:      {consensus['confidence']:.0%}")
    emit(f"  Uebereinstimmung: {consensus['valid_responses']}/{consensus['total_agents']} Agenten")
    emit(f"  Stimmen:         {consensus['votes']}")
    emit(f"{'=' * 60}")
    emit(f"  Dauer:           {elapsed:.1f}s")
    emit(f"  Input-Tokens:    {total_input}")
    emit(f"  Output-Tokens:   {total_output}")
    emit(f"  Kosten:          ${total_cost:.6f}")
    emit(f"{'=' * 60}")

    return {
        "consensus": consensus,
        "individual_results": results,
        "stats": {
            "elapsed_s": elapsed,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": total_cost,
        },
    }


# --- CLI ---


def main():
    parser = argparse.ArgumentParser(
        description="Konsensus-Schwarm: Mehrere LLM-Agenten beantworten dieselbe Frage"
    )
    parser.add_argument(
        "question", nargs="?", default=None,
        help="The question (alternative: --question)"
    )
    parser.add_argument(
        "--question", "-q", dest="question_flag",
        help="The question (alternative as flag)"
    )
    parser.add_argument(
        "--agents", "-a", type=int, default=DEFAULT_AGENTS,
        help=f"Number of agents (default: {DEFAULT_AGENTS})"
    )
    parser.add_argument(
        "--workers", "-w", type=int, default=DEFAULT_WORKERS,
        help=f"Parallel threads (default: {DEFAULT_WORKERS})"
    )
    parser.add_argument(
        "--mode", "-m", choices=["answer", "classify", "boolean"],
        default="answer",
        help="Mode: answer (free), classify (categories), boolean (yes/no)"
    )
    parser.add_argument(
        "--categories", "-c",
        help="Comma-separated categories for classify mode"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Cost estimation only, no API call"
    )
    parser.add_argument(
        "--model", default=os.getenv("SWARM_CONSENSUS_MODEL", MODEL),
        help=f"Anthropic model ID (default: {MODEL})"
    )
    parser.add_argument("--input-cost", type=float, help="USD per 1M input tokens")
    parser.add_argument("--output-cost", type=float, help="USD per 1M output tokens")
    parser.add_argument(
        "--max-budget-usd", type=float,
        help="Conservative cost ceiling; required for live runs",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Ausgabe als JSON"
    )

    args = parser.parse_args()

    question = args.question or args.question_flag
    if not question:
        parser.error("Question required (as argument or --question)")

    categories = None
    if args.categories:
        categories = [c.strip() for c in args.categories.split(",")]

    if (args.input_cost is None) != (args.output_cost is None):
        parser.error("--input-cost and --output-cost must be supplied together")
    cost_override = None
    if args.input_cost is not None:
        cost_override = {"input": args.input_cost, "output": args.output_cost}

    result = run_consensus(
        question=question,
        num_agents=args.agents,
        workers=args.workers,
        mode=args.mode,
        categories=categories,
        dry_run=args.dry_run,
        model=args.model,
        quiet=args.json_output,
        cost_per_1m=cost_override,
        max_budget_usd=args.max_budget_usd,
    )

    if args.json_output and args.dry_run:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.json_output:
        # JSON-Ausgabe (ohne individuelle Details fuer Kompaktheit)
        output = {
            "question": question,
            "mode": args.mode,
            "consensus_answer": result["consensus"]["consensus_answer"],
            "confidence": result["consensus"]["confidence"],
            "votes": result["consensus"]["votes"],
            "tie": result["consensus"]["tie"],
            "agents": result["consensus"]["total_agents"],
            "stats": result["stats"],
        }
        print(f"\n{json.dumps(output, ensure_ascii=False, indent=2)}")

    # Exit-Code: 0 wenn Confidence >= 60%, sonst 1
    if not args.dry_run:
        confidence = result.get("consensus", {}).get("confidence", 0)
        sys.exit(0 if confidence >= 0.6 else 1)


if __name__ == "__main__":
    main()
