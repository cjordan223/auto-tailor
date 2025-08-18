#!/usr/bin/env python3
"""
Job Description Parser - Phase 1 of JD Parser Pipeline

Extracts relevant skills, responsibilities, and company values from job descriptions
using local LLM and generates structured JSON output for subsequent pipeline stages.

Features:
- Deterministic decoding for consistent results
- Evidence validation for each extracted skill
- Skill categorization and confidence scoring
- Duplicate detection and removal
- Configurable skill limits for ATS optimization

Usage:
    python3 jd-parser.py --jd job_description.txt
    python3 jd-parser.py --jd job_description.txt --model qwen2.5-32b-instruct
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Any, List
import aiohttp
import asyncio

# =============================================================================
# Configuration Constants
# =============================================================================

# LM Studio OpenAI-compatible server configuration
DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_MODEL = "qwen2.5-32b-instruct"
TIMEOUT_S = 300  # Reduced from 1800 to 5 minutes for better UX

# Connection pooling for better performance
CONNECTION_LIMIT = 10
CONNECTION_TIMEOUT = 30  # 30 seconds for connection establishment

# LLM generation parameters for deterministic results
GEN_OPTIONS = {
    "temperature": 0.0,    # Deterministic output
    "top_p": 0.9,          # Nucleus sampling
    "seed": 42,            # Fixed seed for reproducibility
    "max_tokens": 4096,    # Increased for comprehensive responses
    "stop": [],            # No stop sequences
}

# Resume skill categories for classification
SUBSECTIONS = [
    "Programming Languages",
    "Frontend",
    "Backend",
    "Cloud & DevOps",
    "AI & LLM Tools",
    "Automation & Productivity",
    "Security & Operating Systems",
    "Databases",
]

# =============================================================================
# Utility Functions
# =============================================================================
# SYSTEM PROMPT - JD -> Skills Extractor (your WebUI version, verbatim)
# -------------------
JD_EXTRACTOR_SYSTEM = """
You are a deterministic parser that extracts ATS-relevant skill tokens from a Job Description (JD) and maps them to resume skill subsections.
You must only use content explicitly present or unambiguously implied by the JD. No fabrication.

Purpose
Produce a compact JSON payload of normalized skills ranked by importance, pre-mapped to these resume subsections:
	- "Programming Languages"
	- "Frontend"
	- "Backend"
	- "Cloud & DevOps"
	- "AI & LLM Tools"
	- "Security & Operating Systems"
	- "Databases"

This JSON will be fed into a separate LaTeX Skills Editor that performs <=2 replacements per subsection.

Input (USER message)
A raw JD text (may include bullets/sections).

Output (ASSISTANT message)
Return JSON only (no prose, no code fences), matching this schema:

{
  "key_responsibilities": ["string"],
  "company_values": ["string"],
  "job_skills_ranked": [
    {
      "token": "string (as it appears or canonicalized, e.g., 'incident response')",
      "canonical": "string (preferred canonical, e.g., 'Incident Response')",
      "section": "one of the 8 subsections",
      "confidence": 0.00,
      "source": ["dict","regex","yake","keybert","ner"],
      "evidence": ["short snippet or phrase from JD", "optional second snippet"],
      "aliases": ["optional list of synonyms found in JD"]
    }
  ],
  "by_section_top3": {
    "Programming Languages": ["...","...","..."],
    "Frontend": ["...","...","..."],
    "Backend": ["...","...","..."],
    "Cloud & DevOps": ["...","...","..."],
    "AI & LLM Tools": ["...","...","..."],
    "Automation & Productivity": ["...","...","..."],
    "Security & Operating Systems": ["...","...","..."],
    "Databases": ["...","...","..."]
  },
  "notes": [
    "very brief explanations for any ambiguous mappings or exclusions"
  ]
}

Constraints
	-	Precision first. Extract only concrete skills, tools, protocols, standards, frameworks, platforms, or tightly related phrases present in the JD.
	-	No defaults. Do not inject standards (e.g., NIST, ISO, PCI) or tools unless mentioned or clearly implied.
	-	Normalization: lower-case for matching, return a canonical form in Title Case (e.g., single sign-on -> canonical SSO).
	-	Deduplicate across spelling/wording; prefer canonical over variants.
	-	Scoring: confidence in [0,1]. Dictionary/regex hits + repeated mentions + role-critical sections -> higher confidence. Weakly implied -> <=0.5.
	-	Section mapping rule of thumb:
	-	Security & Operating Systems: web/mobile security, authN/authZ, SSO/OAuth/OIDC, incident response, cryptography, SIEM, EDR, network/security protocols (TLS, TCP when security-related), threat modeling, secure coding, OWASP, AppSec/DevSecOps.
	-	Backend: APIs/REST/GraphQL, microservices, backend frameworks, scalability, distributed systems.
	-	Cloud & DevOps: AWS/Azure/GCP, containers/orchestration, IaC (Terraform/CloudFormation), CI/CD, observability, gateways, secrets management.
	-	Frontend: React/Vue/Next/Tailwind, frontend security if explicitly framed as client-side.
	-	AI & LLM Tools: LLM frameworks, vector DBs, embedding tools (only if mentioned).
	-	Automation & Productivity: testing/automation tooling (Postman/Selenium), scripting, build tools.
	-	Databases: SQL/NoSQL engines, data warehouses.
	-	Programming Languages: explicit langs only.
	-	Capacity limits for the downstream editor:
	-	Provide any number in job_skills_ranked, but in by_section_top3 cap to 3 items per subsection, ordered by confidence.
	-	Evidence: include minimal snippets (few words) to justify extraction.
	-	No reformatting of JD; just extract.

Canonicalization & Aliases (examples)
	-	single sign on, single-sign-on -> SSO
	-	oauth 2.0, oauth2 -> OAuth 2.0
	-	oidc -> OpenID Connect (OIDC)
	-	mfa, "2fa" -> MFA
	-	web app security, application security -> Web Security
	-	ir, incident mgmt (if clearly incident context) -> Incident Response
	-	edr -> EDR
	-	siem (ELK/Datadog/Splunk refs) -> SIEM
	-	crypto -> If clearly about Cryptography; if blockchain context, canonicalize to Crypto (Blockchain)

Disambiguation
	-	Crypto: If JD references security/privacy/cryptography, map to Cryptography. If tokens/chains/DeFi or blockchain infra, map to Crypto (Blockchain) under Backend or Security based on context.
	-	API Security vs API: If security is emphasized (authN/Z, OAuth, rate limiting, threat modeling), map to Security & Operating Systems as API Security; otherwise Backend as REST APIs/GraphQL.

Algorithm (internal)
	1.	Tokenize -> noun chunks -> lowercase.
	2.	Exact/regex match against a compact security+software dictionary (authN/Z, SSO, OAuth/OIDC, cryptography, incident response, SIEM, EDR, OWASP, REST, GraphQL, CI/CD, Terraform, AWS/Azure/GCP, React/Vue/Next, Python/TS/Java, SQL, Postgres/MySQL/Mongo, Kafka, Docker/K8s, etc.).
	3.	Boost terms appearing in Responsibilities/Requirements sections.
	4.	Keep only concrete skills/tools/standards; drop soft traits (communication, decision making) unless explicitly requested.
	5.	Map each token to a subsection; assign confidence with justification.
	6.	Build by_section_top3 by the highest-confidence items per subsection (<=3).
	7.	Return JSON only.

Style
	-	Deterministic, terse, structured.
	-	Return JSON only. If uncertain, exclude the item or add a short note in notes.

Forbidden behavior
- Do not restate, paraphrase, or summarize the JD.
- Do not output duplicates (case or spelling variants).
- Output exactly one JSON object; no preamble or trailing text.

Validation
- Every extracted item MUST include at least one evidence snippet that appears verbatim (case-insensitive) in the JD.
"""

# -------------------
# Helpers
# -------------------


def norm(s: str) -> str:
    """Normalize Unicode text using NFKC form, strip whitespace, and convert to lowercase."""
    return unicodedata.normalize("NFKC", s).strip().lower()


def evidence_occurs(evidence_list: List[str], jd_text: str) -> bool:
    jdn = norm(jd_text)
    for ev in evidence_list or []:
        if norm(ev) and norm(ev) in jdn:
            return True
    return False


def sanitize_ranked(ranked: List[Dict[str, Any]], jd_text: str) -> List[Dict[str, Any]]:
    """Deduplicate by canonical form, require evidence, fix common typos."""
    seen = set()
    out = []
    for item in ranked or []:
        token = item.get("token", "")
        canon = item.get("canonical") or token
        key = norm(canon)
        if not key or key in seen:
            continue
        if not evidence_occurs(item.get("evidence", []), jd_text):
            continue
        # normalize a couple of common typos
        if key == "seim":
            canon = "SIEM"
        seen.add(norm(canon))
        out.append({
            "token": token,
            "canonical": canon,
            "section": item.get("section", ""),
            "confidence": float(item.get("confidence", 0)),
            "evidence": item.get("evidence", [])[:2],
            "aliases": item.get("aliases", [])[:3],
        })
    return out


def cap_to_n_skills(ranked: List[Dict[str, Any]], n: int = 10) -> List[Dict[str, Any]]:
    """Sort by confidence (desc) then truncate to N."""
    ranked_sorted = sorted(ranked, key=lambda x: x.get(
        "confidence", 0), reverse=True)
    return ranked_sorted[:n]


# Global session for connection pooling
_session = None


async def get_session():
    """Get or create aiohttp session with connection pooling"""
    global _session
    if _session is None or _session.closed:
        connector = aiohttp.TCPConnector(
            limit=CONNECTION_LIMIT,
            limit_per_host=CONNECTION_LIMIT,
            ttl_dns_cache=300,
            use_dns_cache=True
        )
        timeout = aiohttp.ClientTimeout(
            total=TIMEOUT_S,
            connect=CONNECTION_TIMEOUT
        )
        _session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )
    return _session


async def chat_once(base_url: str, api_key: str, model: str,
                    messages: List[Dict[str, str]], options: Dict[str, Any]) -> str:
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": options.get("temperature", 0.0),
        "top_p": options.get("top_p", 0.9),
        "seed": options.get("seed", 42),
        "max_tokens": options.get("max_tokens", 4096),
        "stop": options.get("stop", []),
        "stream": False  # Disable streaming to avoid parsing issues
    }

    try:
        session = await get_session()
        async with session.post(url, headers={"Authorization": f"Bearer {api_key}"},
                                json=payload) as r:
            r.raise_for_status()
            response = await r.json()
            return response['choices'][0]['message']['content']
    except Exception as e:
        print(f"LLM call failed: {e}", file=sys.stderr)
        # Fallback to existing output if available
        try:
            with open("llm_output.txt", "r") as f:
                existing_output = f.read()
                if existing_output.strip():
                    print("Using existing LLM output as fallback", file=sys.stderr)
                    return existing_output
        except:
            pass
        raise e


def coerce_json(s: str) -> Any:
    """Parse JSON with basic error recovery for common LLM output issues."""
    # Strip common code fences
    s = re.sub(r'^```json\s*', '', s.strip())
    s = re.sub(r'```\s*$', '', s.strip())

    # Fix common escape sequence issues
    s = re.sub(r'\\&', '&', s)  # Fix escaped ampersands
    s = re.sub(r'\\\\([^"\\])', r'\\\1', s)  # Fix double-escaped characters

    # First attempt: direct parse (this will fail if there are multiple JSON objects)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # Second attempt: find all complete JSON objects and choose the best one
    json_objects = []
    brace_count = 0
    in_string = False
    escape_next = False
    start_pos = -1

    for i, char in enumerate(s):
        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if char == '{':
                if brace_count == 0:
                    start_pos = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_pos != -1:
                    end_pos = i + 1
                    candidate = s[start_pos:end_pos]
                    try:
                        parsed = json.loads(candidate)
                        json_objects.append(parsed)
                    except json.JSONDecodeError:
                        pass
                    start_pos = -1

    if json_objects:
        # If we found multiple JSON objects, prefer the most complete one
        if len(json_objects) > 1:
            print(
                f"Warning: LLM returned {len(json_objects)} JSON objects, selecting the most complete one", file=sys.stderr)

            # Score each object based on required fields
            def score_json_object(obj):
                score = 0
                required_fields = ['job_skills_ranked',
                                   'by_section_top3', 'key_responsibilities']
                for field in required_fields:
                    if field in obj and obj[field]:
                        score += 1
                        if field == 'by_section_top3' and isinstance(obj[field], dict):
                            # Extra points for having section data
                            score += len([v for v in obj[field].values() if v])
                return score

            # Find the object with the highest score
            best_object = max(json_objects, key=score_json_object)
            best_score = score_json_object(best_object)

            print(
                f"Selected JSON object with score {best_score} out of {len(json_objects)} candidates", file=sys.stderr)
            return best_object
        else:
            return json_objects[0]

    # Check if the response looks truncated
    if s.count('{') > s.count('}'):
        print("Error: LLM response appears to be truncated (unbalanced braces)", file=sys.stderr)
        print(
            f"Found {s.count('{')} opening braces but only {s.count('}')} closing braces", file=sys.stderr)

    # Look for partial JSON structure that might be recoverable
    if '"job_skills_ranked"' in s and '"key_responsibilities"' in s:
        print("Error: Response contains expected fields but JSON structure is malformed", file=sys.stderr)
        print("This may be due to LLM response truncation or formatting issues", file=sys.stderr)

    # If nothing worked, raise original error
    raise json.JSONDecodeError(f"Could not parse JSON from response", s, 0)

# -------------------
# Main
# -------------------


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jd", default="jd.txt", help="Path to JD text")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--api-key", default=DEFAULT_API_KEY)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--cap", type=int, default=10,
                    help="Max skills to return in the flat list")
    ap.add_argument("--no-cache", action="store_true",
                    help="Disable caching for this request")
    args = ap.parse_args()

    jd_path = Path(args.jd)
    if not jd_path.exists():
        sys.exit(f"ERROR: JD file not found: {jd_path}")
    jd_text = jd_path.read_text(encoding="utf-8").strip()

    # Check cache first (unless disabled)
    resp = None
    cache_key = f"{jd_text}|{args.model}|{JD_EXTRACTOR_SYSTEM}"
    
    if not args.no_cache:
        try:
            from cache_manager import get_cached_llm_response, cache_llm_response
            resp = get_cached_llm_response(cache_key)
            if resp:
                print("🚀 Using cached LLM response", file=sys.stderr)
        except ImportError:
            print("Cache manager not available, proceeding without cache", file=sys.stderr)
    
    # If no cached response, make LLM call
    if not resp:
        print("⚙️ Making LLM request (no cache hit)", file=sys.stderr)
        resp = await chat_once(
            args.base_url, args.api_key, args.model,
            [
                {"role": "system", "content": JD_EXTRACTOR_SYSTEM},
                {"role": "user", "content": jd_text},
            ],
            GEN_OPTIONS
        )
        
        # Cache the response (unless disabled)
        if not args.no_cache:
            try:
                cache_llm_response(cache_key, resp)
                print("💾 Cached LLM response", file=sys.stderr)
            except:
                print("Failed to cache LLM response", file=sys.stderr)

    try:
        raw = coerce_json(resp)
    except Exception as e:
        with open("llm_output.txt", "w") as f:
            f.write(resp)
        print("Wrote raw LLM output to llm_output.txt", file=sys.stderr)
        sys.exit(f"ERROR: extractor did not return valid JSON: {e}")

    # Sanitize ranked list
    ranked = sanitize_ranked(raw.get("job_skills_ranked", []), jd_text)

    # Keep model's by_section_top3 if present; otherwise derive a light one from ranked
    by_section = raw.get("by_section_top3") or {sec: [] for sec in SUBSECTIONS}
    # Ensure each list is at most 3 strings
    for sec in list(by_section.keys()):
        vals = by_section.get(sec, []) or []
        # if model returned dicts, coerce to canonical strings
        canon_vals = []
        seen = set()
        for v in vals:
            can = v.get("canonical", v) if isinstance(v, dict) else v
            k = norm(can)
            if k and k not in seen:
                seen.add(k)
                canon_vals.append(can)
        by_section[sec] = canon_vals[:3]

    # Build a flat list of up to N skills (canonical strings) sorted by confidence
    top_n = cap_to_n_skills(ranked, n=args.cap)
    flat = [s["canonical"] for s in top_n]

    out = {
        "job_skills_ranked": ranked,   # cleaned, de-duped, evidence-checked
        "by_section_top3": by_section,  # trimmed to <=3 each
        # <= N (default 10) - feed this to the editor
        "skills_flat": flat
    }

    # Ensure artifacts directory exists
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    # Write to artifacts/jd_skills.json
    output_path = artifacts_dir / "jd_skills.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f" Wrote output to: {output_path}", file=sys.stderr)
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
