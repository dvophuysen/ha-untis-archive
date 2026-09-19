"""Book-order regressions: continuation, gaps, boxes and repeated headings."""
from backend.vocab_sequence import Boundary as B, Page, compile_book, lexical_key


def row(word):
    return {'foreign_word': word, 'meanings': ['Bedeutung']}


def page(n, words, boundaries=(), begins='continuation'):
    return Page(n, f'source-{n}', tuple(row(w) for w in words), tuple(boundaries), begins)


def opening(at, title, level=0, kind='section'):
    return B(at, 'open', title, level, kind, title)


def titles(result, occurrence):
    nodes = {n['id']: n['title'] for n in result.nodes}
    return [nodes[n] for n in result.occurrences[occurrence]['node_ids']]


def test_continuation_before_midpage_heading_inherits_previous_page():
    result = compile_book([
        page(162, ['a'], [opening(0, 'Unit 1'), opening(0, 'Text A', 1)], 'new'),
        page(163, ['b', 'c'], [opening(1, 'Text B', 1)]),
        page(164, ['d'], [B(0, 'running', 'Unit 1', evidence='page header')]),
    ], start_page=162)
    assert result.structurally_valid
    assert titles(result, 1) == ['Unit 1', 'Text A']
    assert titles(result, 2) == ['Unit 1', 'Text B']
    assert titles(result, 3) == ['Unit 1', 'Text B']
    assert len(result.nodes) == 3


def test_middle_of_book_cannot_invent_inherited_unit_from_running_header():
    result = compile_book([page(164, ['a'], [B(0, 'running', 'Unit 1', evidence='header')])], start_page=160)
    assert not result.structurally_valid
    assert result.occurrences[0]['node_ids'] == []
    assert {'missing_predecessor', 'unmatched_running_header', 'unresolved_membership'} <= {i['code'] for i in result.issues}


def test_gap_clears_context_even_when_an_earlier_unit_is_known():
    result = compile_book([page(10, ['a'], [opening(0, 'Lektion 1')], 'new'),
                           page(12, ['b', 'c'], [opening(1, 'Lektion 2')])], start_page=10)
    assert not result.structurally_valid
    assert titles(result, 1) == []
    assert titles(result, 2) == ['Lektion 2']


def test_explicitly_verified_empty_page_preserves_context():
    result = compile_book([page(10, ['a'], [opening(0, 'Lektion 1')], 'new'),
                           page(11, []), page(12, ['b'])], start_page=10)
    assert result.structurally_valid
    assert titles(result, 1) == ['Lektion 1']


def test_box_has_explicit_end_and_can_span_pages():
    result = compile_book([
        page(164, ['a', 'b'], [opening(0, 'Unit 1'), opening(0, 'Text A', 1),
                              opening(1, 'At the airport', 2, 'box')], 'new'),
        page(165, ['c', 'd', 'e'], [B(1, 'close', evidence='bottom border', target='p164:r1:n2'),
                                   opening(2, 'Story: Where I belong', 1)]),
    ], start_page=164)
    assert result.structurally_valid
    assert titles(result, 2) == ['Unit 1', 'Text A', 'At the airport']
    assert titles(result, 3) == ['Unit 1', 'Text A']
    assert titles(result, 4) == ['Unit 1', 'Story: Where I belong']


def test_new_section_does_not_silently_close_box():
    result = compile_book([page(1, ['a', 'b'], [opening(0, 'Unit'), opening(0, 'Box', 1, 'box'),
                                              opening(1, 'Text', 1)], 'new')], start_page=1)
    assert not result.structurally_valid
    assert 'unclosed_box' in {i['code'] for i in result.issues}


def test_box_end_closes_its_subsections_before_following_unit():
    result = compile_book([page(211, ['beach', 'swim', 'deaf'], [
        opening(0, 'Welcome back!'), opening(0, 'Holiday words', 1, 'box'),
        opening(0, 'places', 2), opening(1, 'activities', 2),
        B(2, 'close', target='p211:r0:n1', evidence='bottom border'),
        opening(2, 'Unit 1'),
    ], 'new')], start_page=211)
    assert result.structurally_valid
    assert titles(result, 0) == ['Welcome back!', 'Holiday words', 'places']
    assert titles(result, 1) == ['Welcome back!', 'Holiday words', 'activities']
    assert titles(result, 2) == ['Unit 1']


def test_repeated_titles_are_distinct_memberships_sorted_by_book_not_submission():
    result = compile_book([page(2, ['b'], [opening(0, 'Unit 2'), opening(0, 'Text A', 1)], 'new'),
                           page(1, ['a'], [opening(0, 'Unit 1'), opening(0, 'Text A', 1)], 'new')], start_page=1)
    assert result.structurally_valid
    assert [o['page'] for o in result.occurrences] == [1, 2]
    assert len({n['id'] for n in result.nodes}) == 4
    assert titles(result, 0) == ['Unit 1', 'Text A']
    assert titles(result, 1) == ['Unit 2', 'Text A']


def test_overlapping_spreads_must_be_resolved_before_compiling():
    assert not compile_book([page(1, []), page(1, [])], start_page=1).structurally_valid


def test_contradictory_page_start_and_missing_evidence_block_publication():
    result = compile_book([page(1, ['a'], [B(0, 'open', 'Unit')], 'continuation')], start_page=1)
    assert not result.structurally_valid
    assert {'page_start_conflict', 'boundary_without_evidence'} <= {i['code'] for i in result.issues}


def test_same_word_deduplicates_across_occurrences_but_not_different_senses_or_accents():
    assert lexical_key('SPANISCH', row('más')) == lexical_key('spanisch', row('  MÁS '))
    assert lexical_key('spanisch', row('más')) != lexical_key('spanisch', row('mas'))
    assert lexical_key('englisch', row('to go')) != lexical_key('englisch', row('go away'))
    assert lexical_key('englisch', row('bank')) != lexical_key('englisch', {'foreign_word': 'bank', 'meanings': ['Ufer']})
