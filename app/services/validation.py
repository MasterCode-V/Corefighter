"""Article validation workflow (workflow 6)."""
from __future__ import annotations

from typing import List

from app.enums import ContentRuleType, ValidationOutcome
from app.models import ArticleVersion, ContentRule

MIN_BODY_LENGTH = 200
MAX_BODY_LENGTH = 20000


def validate_article(version: ArticleVersion, rules: List[ContentRule]) -> dict:
    """Run all validation checks and return a structured result.

    Result: {outcome, checks: [{name, status, detail}], errors, warnings}
    """
    checks: List[dict] = []
    errors: List[str] = []
    warnings: List[str] = []

    full_text = version.full_text

    # 1. Required sections
    missing = [
        name for name, value in (
            ("title", version.title),
            ("introduction", version.introduction),
            ("body", version.body),
        ) if not (value or "").strip()
    ]
    if missing:
        errors.append(f"Missing required sections: {', '.join(missing)}")
        checks.append({"name": "required_sections", "status": "failed", "detail": missing})
    else:
        checks.append({"name": "required_sections", "status": "passed"})

    # 2. Article length
    length = len(version.body or "")
    if length < MIN_BODY_LENGTH:
        errors.append(f"Article body too short ({length} < {MIN_BODY_LENGTH})")
        checks.append({"name": "length", "status": "failed", "detail": length})
    elif length > MAX_BODY_LENGTH:
        warnings.append(f"Article body very long ({length})")
        checks.append({"name": "length", "status": "warning", "detail": length})
    else:
        checks.append({"name": "length", "status": "passed", "detail": length})

    # 3. Prohibited words
    lowered = full_text.lower()
    hit_words = [
        r.value for r in rules
        if r.rule_type == ContentRuleType.PROHIBITED_WORD and r.is_active
        and r.value and r.value.lower() in lowered
    ]
    if hit_words:
        errors.append(f"Prohibited words present: {', '.join(hit_words)}")
        checks.append({"name": "prohibited_words", "status": "failed", "detail": hit_words})
    else:
        checks.append({"name": "prohibited_words", "status": "passed"})

    # 4. Prohibited contexts (soft check -> warning)
    hit_contexts = [
        r.value for r in rules
        if r.rule_type == ContentRuleType.PROHIBITED_CONTEXT and r.is_active
        and r.value and r.value.lower() in lowered
    ]
    if hit_contexts:
        warnings.append(f"Possible prohibited context: {', '.join(hit_contexts)}")
        checks.append({"name": "prohibited_contexts", "status": "warning", "detail": hit_contexts})
    else:
        checks.append({"name": "prohibited_contexts", "status": "passed"})

    # 5. Article structure (needs headings)
    if not version.headings:
        warnings.append("Article has no structured headings")
        checks.append({"name": "structure", "status": "warning"})
    else:
        checks.append({"name": "structure", "status": "passed", "detail": len(version.headings)})

    # 6. Unsupported / uncertain information (heuristic)
    uncertainty_markers = ["かもしれません", "たぶん", "おそらく", "unknown", "not sure", "??"]
    if any(marker in lowered for marker in uncertainty_markers):
        warnings.append("Article contains uncertain/unsupported statements")
        checks.append({"name": "certainty", "status": "warning"})
    else:
        checks.append({"name": "certainty", "status": "passed"})

    if errors:
        outcome = ValidationOutcome.FAILED
    elif warnings:
        outcome = ValidationOutcome.WARNING
    else:
        outcome = ValidationOutcome.PASSED

    return {
        "outcome": outcome.value,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }
