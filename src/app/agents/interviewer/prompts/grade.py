from langchain_core.prompts import ChatPromptTemplate

GRADE_PROMPT = ChatPromptTemplate.from_template(
    """
    You are a rigorous technical examiner. Grade this response about {skill}.
    Question (difficulty {difficulty}/5): {question}
    Response: {response}

    Grading Rubric:
    1 - Incorrect, irrelevant, or contains forbidden factual errors
    2 - Partially correct but with significant gaps or misconceptions
    3 - Mostly correct with minor issues; meets basic expectations
    4 - Strong answer with concrete steps/code and clear understanding
    5 - Excellent technical precision with complete, accurate details

    Rules:
    - Cap score at 1 if response contains any forbidden factual errors for this skill
    - Penalize generic, off-topic, or hand-wavy answers that drift from the question
    - Reward specific, correct implementation steps or minimal working code examples
    - Focus purely on technical accuracy and completeness
    - Ignore confidence, verbosity or buzzwords

    Output JSON only:
    {{
        "score": <integer 1-5>,
        "reasoning": "<2-3 sentences on specific correct/incorrect points>"
    }}
    """
)
