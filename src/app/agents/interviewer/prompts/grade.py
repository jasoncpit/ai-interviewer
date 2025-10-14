from langchain_core.prompts import ChatPromptTemplate

GRADE_PROMPT = ChatPromptTemplate.from_template(
    """
    Grade this technical interview response about {skill}.
    Question (difficulty {difficulty}/5): {question}
    Response: {response}

    Grading Rubric (be strict and conservative):
    1 - Incorrect or irrelevant answer showing minimal understanding
    2 - Partially correct but with significant gaps or misconceptions
    3 - Mostly correct with minor issues; meets basic expectations
    4 - Strong answer demonstrating clear understanding and good communication
    5 - Excellent answer showing deep knowledge, clear explanation, and technical precision

    Consider ONLY the technical correctness and completeness relative to the question. Do NOT reward confidence, verbosity, or buzzwords if the content is wrong.
    If the answer is generic, hand-wavy, off-topic, or fails to address core aspects of the question, it should be scored 1 or 2.
    Penalize factual errors, misconceptions, and failure to provide key steps, definitions, or rationale.

    Consider:
    - Technical accuracy and completeness
    - Clear communication and structured response
    - Depth of understanding shown
    - Appropriate use of technical terminology
    - Problem-solving approach (if applicable)

    Provide:
    1. Score (1-5)
    2. Brief justification (2-3 sentences) explaining specific correct/incorrect points with reference to the question
    """
)
