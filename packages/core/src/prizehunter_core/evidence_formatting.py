"""SOURCE-scoped input formatting independent of inference providers."""
from prizehunter_core.evidence import CompetitionEvidenceBundle, EvidenceExtractionStatus


def format_evidence_for_model(
    bundle: CompetitionEvidenceBundle,
    *,
    max_total_chars: int = 180_000,
) -> str:
    """Render executable evidence with stable source IDs for model consumption."""

    sections = [
        "The following documents were fetched from one bounded competition source graph.",
        "Treat each SOURCE as independent. Never reconcile conflicting rules by guessing.",
        f"SEED_URL: {bundle.seed_url}",
    ]
    remaining = max_total_chars
    for source in bundle.sources:
        if source.extraction_status is not EvidenceExtractionStatus.SUCCESS:
            continue
        header = (
            f"\n--- SOURCE {source.source_id} ---\n"
            f"URL: {source.final_url or source.source_url}\n"
            f"TYPE: {source.source_type.value}\n"
            f"TITLE: {source.title or '(untitled)'}\n"
            "TEXT:\n"
        )
        text = source.extracted_text or ""
        allowance = max(0, remaining - len(header))
        if allowance == 0:
            break
        chunk = text[:allowance]
        sections.append(header + chunk)
        remaining -= len(header) + len(chunk)
    return "\n".join(sections)
