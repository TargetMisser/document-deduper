from __future__ import annotations

from collections import defaultdict

from .models import DedupeOptions, DocumentSegment
from .text import comparable_text


def choose_best(segments: list[DocumentSegment], options: DedupeOptions) -> DocumentSegment:
    if options.prefer == "first":
        best = min(segments, key=lambda segment: (segment.source.index, segment.source_index))
    else:
        best = max(segments, key=lambda segment: segment.char_count)
    members: list[str] = []
    for segment in segments:
        members.extend(segment.duplicate_sources or [segment.source_ref])
    best.duplicate_sources = list(dict.fromkeys(members))
    return best


def word_sample(segment: DocumentSegment) -> set[str]:
    return set(comparable_text("\n".join(segment.lines)).split()[:4000])


def similar_same_number_groups(
    segments: list[DocumentSegment], threshold: float
) -> list[list[DocumentSegment]]:
    by_number: dict[str, list[DocumentSegment]] = defaultdict(list)
    for segment in segments:
        if segment.number:
            by_number[segment.number].append(segment)

    groups: list[list[DocumentSegment]] = []
    for candidates in by_number.values():
        if len(candidates) < 2:
            continue
        parents = list(range(len(candidates)))
        samples = [word_sample(segment) for segment in candidates]

        def find(idx: int) -> int:
            while parents[idx] != idx:
                parents[idx] = parents[parents[idx]]
                idx = parents[idx]
            return idx

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parents[root_right] = root_left

        for left in range(len(candidates)):
            for right in range(left + 1, len(candidates)):
                a = samples[left]
                b = samples[right]
                if not a or not b:
                    continue
                similarity = len(a & b) / max(1, min(len(a), len(b)))
                if similarity >= threshold:
                    union(left, right)

        clusters: dict[int, list[DocumentSegment]] = defaultdict(list)
        for idx, segment in enumerate(candidates):
            clusters[find(idx)].append(segment)
        groups.extend(cluster for cluster in clusters.values() if len(cluster) > 1)
    return groups


def dedupe_segments(
    segments: list[DocumentSegment], options: DedupeOptions
) -> tuple[list[DocumentSegment], list[dict[str, object]]]:
    duplicate_groups: list[dict[str, object]] = []

    by_key: dict[str, list[DocumentSegment]] = defaultdict(list)
    for segment in segments:
        by_key[segment.dedupe_key].append(segment)

    chosen: list[DocumentSegment] = []
    for key, group in by_key.items():
        if len(group) == 1:
            group[0].duplicate_sources = [group[0].source_ref]
            chosen.append(group[0])
            continue
        best = choose_best(group, options)
        chosen.append(best)
        duplicate_groups.append(
            {"key": key, "kept": best.source_ref, "members": [segment.source_ref for segment in group]}
        )

    by_fp: dict[str, list[DocumentSegment]] = defaultdict(list)
    for segment in chosen:
        by_fp[segment.fingerprint].append(segment)

    chosen_2: list[DocumentSegment] = []
    for fingerprint, group in by_fp.items():
        if len(group) == 1:
            chosen_2.append(group[0])
            continue
        best = choose_best(group, options)
        chosen_2.append(best)
        duplicate_groups.append(
            {
                "key": f"fingerprint:{fingerprint}",
                "kept": best.source_ref,
                "members": [segment.source_ref for segment in group],
            }
        )

    same_number = similar_same_number_groups(chosen_2, options.similarity_threshold)
    grouped_ids = {id(segment) for group in same_number for segment in group}
    chosen_3 = [segment for segment in chosen_2 if id(segment) not in grouped_ids]
    for group in same_number:
        best = choose_best(group, options)
        chosen_3.append(best)
        duplicate_groups.append(
            {
                "key": f"same-number-similar:{best.number}",
                "kept": best.source_ref,
                "members": best.duplicate_sources,
            }
        )

    return chosen_3, duplicate_groups
