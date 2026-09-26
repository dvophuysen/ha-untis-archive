from backend import vocab, vocab_progress as progress


def word(wid, results=(), scope=None):
    attempts = [dict(result=r, seconds=60, created_at='2026-09-20T12:00:00', unit_scope=scope) for r in results]
    return dict(id=wid, state={'s1': vocab.replay(attempts), 's2': vocab.replay([])})


def test_colors_distinguish_only_wrong_mixed_mastered_and_unseen():
    words = [word(1, ['incorrect']), word(2, ['correct']), word(3, ['correct', 'incorrect']),
             word(4, ['correct', 'correct']), word(5)]
    # Auf Anhieb richtig gilt als vorläufig sicher (D212).
    assert progress.summarize(words + [words[0]]) == dict(wrong=1, uncertain=1, secure=2, new=1, total=5)
    assert progress.summarize(words, 's2') == dict(wrong=0, uncertain=0, secure=0, new=5, total=5)


def test_started_total_excludes_future_units_and_deduplicates_shared_words(monkeypatch):
    shared = word(1, ['correct'], 'u1')
    selections = {'u1': [shared, word(2)], 'u2': [shared, word(3)], 'u3': [word(4)]}
    monkeypatch.setattr(vocab, 'cards', lambda account, subject, unit, *args, **kwargs: selections[unit])
    units = [dict(unit=u, sections=[]) for u in selections]
    result = progress.annotate(1, 'Spanisch', units)
    assert result['started_units'] == 1 and result['progress']['total'] == 2
    assert [u['started'] for u in units] == [True, False, False]
    selections['u2'][1] = word(3, ['incorrect'], 'u2')
    result = progress.annotate(1, 'Spanisch', units)
    assert result['started_units'] == 2 and result['progress']['total'] == 3


def test_historical_shared_word_does_not_mark_all_future_units_started(monkeypatch):
    shared = word(1, ['correct'])
    selections = {'u1': [shared, word(2, ['incorrect'])], 'u2': [shared, word(3)]}
    monkeypatch.setattr(vocab, 'cards', lambda account, subject, unit, *args, **kwargs: selections[unit])
    units = [dict(unit=u, sections=[]) for u in selections]
    assert progress.annotate(1, 'Spanisch', units)['started_units'] == 1
    assert not units[1]['started']


def test_long_correct_answer_does_not_destroy_established_mastery():
    original = [dict(result='correct', seconds=s, created_at=d) for s,d in
                [(4,'2026-09-16'), (5,'2026-09-16'), (180,'2026-09-20')]]
    before = [dict(a) for a in original]
    assert vocab.replay(original)['stage'] == 'gefestigt'
    assert original == before
