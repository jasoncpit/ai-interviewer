from langchain_core.prompts import ChatPromptTemplate

GRADE_PROMPT = ChatPromptTemplate.from_template(
    """
    You are a rigorous technical examiner. Assess the candidate's response about {skill}.

    Question (difficulty {difficulty}/5):
    {question}

    Candidate response:
    {response}

    Evaluate the answer by scoring each aspect on a 1–5 scale using the mini-rubrics below.
    Provide a short note for every aspect that cites concrete evidence (or the lack of it) from the response.
       - coverage: Does the answer address every part of the question? Penalise omissions or digressions.
       - technical_depth: Are key PyTorch Lightning APIs, callbacks, or implementation details described accurately? Require code-level insight for ≥4.
       - evidence: Are there specific examples, metrics, trade-offs, or results? Without real evidence the score must be ≤3.
       - communication: Is the explanation structured, precise, and does it note limitations or uncertainties?
       Aspect guide: 1 = incorrect/off-topic, 2 = partial with major gaps, 3 = baseline accurate but light on detail, 4 = strong with concrete steps, 5 = exemplary and exhaustive.

    If the response contains a factual or safety-critical error, set factual_error to true and score every aspect as 1.

    Output strict JSON only (do NOT compute a final score):
    {{
        "reasoning": "<2-3 sentence overall justification>",
        "factual_error": <true | false>,
        "aspects": {{
            "coverage": {{"score": <int>, "notes": "<evidence-based note>"}},
            "technical_depth": {{"score": <int>, "notes": "<note>"}},
            "evidence": {{"score": <int>, "notes": "<note>"}},
            "communication": {{"score": <int>, "notes": "<note>"}}
        }}
    }}

    Do not include any additional text outside the JSON object.
    """
)
