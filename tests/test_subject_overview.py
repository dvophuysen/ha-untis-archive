"""Graphical overview must not turn missing feedback into poor performance."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'schul_cockpit'))
from backend.routers.oral import summarize_goals


class Catalog:
    def resolve(self, name, sid):
        return {'label': name}


def goal(key, rating, sources, sid=1):
    return dict(kind='lesson', key=key, subject='Deutsch', subject_id=sid,
                date='2026-09-13', rating=rating, title=key, state='', url='#/learning',
                sources=sources, source_count=len(sources), uncertain_count=0)


def test_unknown_topics_and_observation_history_are_not_ability_scores():
    older = dict(id=1, date='2026-09-01', start_time=800, rating=1)
    newer = dict(id=2, date='2026-09-08', start_time=900, rating=3)
    missing = dict(id=3, date='2026-09-09', start_time=800, rating=None)
    supervision = dict(id=4, date='2026-09-10', start_time=800, rating=4)
    # A topic's latest assessment is positive despite earlier difficulty.
    result = summarize_goals([
        goal('improved', 3, [newer, older]),
        goal('unknown', None, [missing, supervision]),
        goal('partial', 2, [dict(id=5, date='2026-09-08', start_time='08:00', rating=2), older]),
        goal('other-account-subject', None, [], sid=2),
        dict(kind='activity'),
    ], Catalog())
    first, second = result
    assert (first['understood_topics'], first['partial_topics'], first['difficult_topics'], first['unrated_topics']) == (1, 1, 0, 1)
    assert [p['lesson_id'] for p in first['feedback_history']] == [1, 5, 2]
    assert first['feedback_count'] == 3  # Duplicate source and non-ratings excluded.
    assert [t['lesson_id'] for t in first['items']] == ['partial']
    assert len(first['topics']) == 3
    assert second['unrated_topics'] == 1 and second['feedback_history'] == []
    assert 'score' not in first and 'trend' not in first
