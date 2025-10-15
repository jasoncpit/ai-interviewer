from langchain_core.prompts import ChatPromptTemplate

QUESTION_PROMPT = ChatPromptTemplate.from_template(
    """
    You are designing a technical interview question to assess {skill}.

    Difficulty: {difficulty} on a 1-5 scale (1=easy, 5=expert).
    Previous question: {previous_question}
    Previous answer summary: {previous_answer}
    Grader reasoning: {previous_reasoning}
    Recent turn history for this skill:
    {recent_history}

    Evidence from candidate profile:
    {evidence_spans}

    Based on the candidate's previous answer and reasoning, ask a natural follow-up question that builds on their response.
    The question should feel like a friendly conversation while still probing their practical expertise in {skill}.
    Keep it concise and focused - it should be answerable in under 2 minutes.

    If there is no previous question/answer, ask an initial question that matches their apparent skill level.

    Return only the question text.
    """
)
