from __future__ import annotations

from interviewer.core.manager import AnswerOutcome, ConversationManager
from interviewer.core.policy_ucb import QuestionArm, UCBPolicy
from interviewer.core.priors import SkillProfile, build_ledger_from_profile
from interviewer.core.state import InterviewState


def make_state(target_verified: int = 1) -> InterviewState:
    ledger = build_ledger_from_profile(
        [
            SkillProfile(
                skill="pytorch",
                source_confidence=0.8,
                years_claimed=4,
                days_since_last_used=30,
            ),
            SkillProfile(
                skill="pandas",
                source_confidence=0.7,
                years_claimed=5,
                days_since_last_used=60,
            ),
        ]
    )
    return InterviewState.from_priors(ledger, target_verified=target_verified)


def participant_outcome(answer: str, seconds: float, score: int) -> AnswerOutcome:
    return AnswerOutcome(answer=answer, seconds=seconds, override_score=score)


def test_conversation_manager_reaches_stop_condition():
    state = make_state(target_verified=1)
    policy = UCBPolicy()
    manager = ConversationManager(state=state, policy=policy)

    # Simulate deterministic answers
    for _ in range(5):
        if state.should_stop():
            break
        arm = QuestionArm(skill="pytorch", strategy="breadth", difficulty="easy")
        state.last_question = manager.generator.generate(state, arm)
        outcome = participant_outcome(
            answer="Discuss gradient clipping and optimizer tweaks.",
            seconds=45.0,
            score=3,
        )
        grade, delta, decision = manager.submit_answer(outcome)
        if decision.should_stop:
            break

    assert state.should_stop()
    assert state.verified_count >= 1
