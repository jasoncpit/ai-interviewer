from langchain_core.prompts import ChatPromptTemplate

QUESTION_PROMPT = ChatPromptTemplate.from_template(
    """
    You are having a friendly technical conversation to learn about the candidate's experience with {skill}.

    Difficulty: {difficulty} on a 1-5 scale (1=easy, 5=expert).
    Previous question: {previous_question}
    Previous answer summary: {previous_answer}
    Grader reasoning: {previous_reasoning}
    Recent turn history for this skill:
    {recent_history}

    Evidence from candidate profile:
    {evidence_spans}

    Continue the conversation naturally by asking a follow-up question that builds on their response. Make them feel comfortable while exploring their practical expertise in {skill}. Keep the tone warm and collaborative.

    The question should be concise and focused - something they can answer comfortably in under 2 minutes.

    If this is the first question, start with a welcoming question that matches their apparent skill level.

    Return only the question text.
    """
)
