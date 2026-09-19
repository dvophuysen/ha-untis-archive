"""Compile page-local evidence in book order, without modifying learning data.

Models transcribe local rows and boundaries. They never decide which previous
page's chapter to inherit. This deterministic pass owns that decision. A gap
invalidates inherited context; a running header cannot repair it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
import hashlib
import json
import unicodedata


@dataclass(frozen=True)
class Boundary:
    at: int  # before this zero-based row; len(rows) is the page end
    action: Literal['open', 'close', 'running']
    title: str = ''
    level: int = 0
    kind: str = 'section'
    evidence: str = ''  # source heading or visible end-of-box evidence
    target: str = ''  # explicit node ID for close; never a fuzzy title


@dataclass(frozen=True)
class Page:
    number: int
    source_hash: str
    rows: tuple[dict, ...]
    boundaries: tuple[Boundary, ...] = ()
    begins: Literal['new', 'continuation', 'unknown'] = 'unknown'


@dataclass
class Compiled:
    nodes: list[dict] = field(default_factory=list)
    occurrences: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    transitions: list[dict] = field(default_factory=list)

    @property
    def structurally_valid(self) -> bool:
        """Structural consistency only; content accuracy needs a separate audit."""
        return bool(self.occurrences) and not self.issues


def exact_text(value: str) -> str:
    """Conservative identity: preserve accents, particles and punctuation."""
    return ' '.join(unicodedata.normalize('NFC', value).split()).casefold()


def lexical_key(subject: str, row: dict) -> str:
    """Only identical, fully specified senses merge automatically.

    A different translation is a review candidate, never a silent sense merge.
    Source memberships and spelling variants remain separate evidence.
    """
    payload = [exact_text(subject), exact_text(row['foreign_word']),
               sorted({exact_text(m) for m in row['meanings']}),
               exact_text(row.get('grammar', '')),
               row.get('forms', {})]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def compile_book(pages: list[Page], *, start_page: int) -> Compiled:
    """Compile from the independently established start of the vocabulary part.

    Each physical page occurs exactly once. Spreads must be split first. Nodes
    have occurrence IDs, so identical headings under different units do not
    collapse. Boxes must be closed explicitly; they do not end at page edges.
    All problems block publication, but the draft remains inspectable.
    """
    out = Compiled()
    stack: list[dict] = []
    expected = start_page

    def issue(page, code, **extra):
        out.issues.append({'page': page, 'code': code, **extra})

    numbers = [p.number for p in pages]
    if len(numbers) != len(set(numbers)):
        issue(None, 'duplicate_physical_page')
        return out
    for page in sorted(pages, key=lambda p: p.number):
        if page.number < start_page:
            issue(page.number, 'before_vocabulary_start')
            continue
        if page.number != expected:
            issue(page.number, 'missing_predecessor', expected=expected)
            stack = []
        expected = page.number + 1
        incoming = [n['id'] for n in stack]
        if not page.source_hash:
            issue(page.number, 'missing_source_hash')
        if page.begins == 'unknown':
            issue(page.number, 'uncertain_page_start')
        events: dict[int, list[Boundary]] = {}
        for boundary in page.boundaries:
            if not 0 <= boundary.at <= len(page.rows):
                issue(page.number, 'boundary_out_of_range')
                continue
            events.setdefault(boundary.at, []).append(boundary)
        new_at_start = any(b.action == 'open' and b.kind != 'box' for b in events.get(0, []))
        if (page.begins == 'new') != new_at_start and page.begins != 'unknown':
            issue(page.number, 'page_start_conflict')
        for position in range(len(page.rows) + 1):
            for b in events.get(position, []):
                if not b.evidence.strip():
                    issue(page.number, 'boundary_without_evidence', position=position)
                    continue
                if b.action == 'running':
                    if not any(exact_text(n['title']) == exact_text(b.title) for n in stack):
                        issue(page.number, 'unmatched_running_header', position=position)
                    continue
                if b.action == 'close':
                    matches = [i for i, n in enumerate(stack) if n['id'] == b.target and n['kind'] == 'box']
                    if not matches:
                        issue(page.number, 'invalid_box_end', position=position)
                    else:
                        index = matches[0]
                        if any(n['kind'] == 'box' for n in stack[index + 1:]):
                            issue(page.number, 'unclosed_nested_box', position=position)
                        del stack[index:]
                    continue
                if b.action != 'open' or not b.title.strip() or b.level < 0:
                    issue(page.number, 'invalid_boundary', position=position)
                    continue
                # A heading cannot implicitly swallow a still-open box.
                if any(n['kind'] == 'box' and n['level'] >= b.level for n in stack):
                    issue(page.number, 'unclosed_box', position=position)
                while stack and stack[-1]['level'] >= b.level:
                    stack.pop()
                if b.level != len(stack) or (b.level == 0 and b.kind == 'box'):
                    issue(page.number, 'missing_parent', position=position)
                    continue
                node = {'id': f'p{page.number}:r{position}:n{len(out.nodes)}',
                        'parent_id': stack[-1]['id'] if stack else None,
                        'title': b.title.strip(), 'kind': b.kind, 'level': b.level,
                        'page': page.number, 'position': position, 'evidence': b.evidence}
                out.nodes.append(node)
                stack.append(node)
            if position == len(page.rows):
                continue
            row = page.rows[position]
            if not row.get('foreign_word', '').strip() or not row.get('meanings'):
                issue(page.number, 'incomplete_row', position=position)
            if not stack:
                issue(page.number, 'unresolved_membership', position=position)
            out.occurrences.append({'page': page.number, 'position': position,
                                    'source_hash': page.source_hash, 'row': row,
                                    'node_ids': [n['id'] for n in stack]})
        out.transitions.append({'page': page.number, 'begins': page.begins,
                                'incoming': incoming, 'outgoing': [n['id'] for n in stack]})
    if any(n['kind'] == 'box' for n in stack):
        issue(pages[-1].number if pages else None, 'unclosed_box_at_end')
    return out
