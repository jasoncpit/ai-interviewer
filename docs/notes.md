

## 12/10/2025

### Prolific Interview Assessment Overview

As part of the prolific interview assessment, I was tasked to design systems that enable high-quality human feedback for AI model evaluation and deployment. The challenge was to design an AI interview system that can engage with participants to vertify their expertise claims.

More specifically, They are asking me to design a system that can process information from participant credentials (CVs,
LinkedIn profiles, Google Scholar), conduct intelligent verification through an AI interviewer approach, and assess expertise in specific domains relevant to AI evaluation tasks.

I will need to prepare a design of the overall architecture for an AI expertise interviewer and verification system and choose ONE component to implement as a POC. I need to prepare to present my approach and implementation within 20 mins.

Core components:
1. Credential Analysis Component - Implement a parser that extracts key skills and expertise claims from a CV, build a system to reconcile information across different sources, or create a skill taxonomy classifier for organizing participant expertise areas.
2. AI Interviewer Component: Design prompt templates that generate domain-specific
verification questions, implement a conversation flow manager that adapts questioning based on responses, or create a mechanism to detect inconsistencies in participant answers.
3. Verification Logic Component: Build a scoring system that evaluates expertise based on response quality, implement a fact-checking mechanism for specific technical claims, or create a confidence estimation system for expertise verification.

Implementation notes:
I am going to use Python as my key programming language. I will use OpenAI API for a base AI model.

What they are looking for:
1. Engineering Fundamentals: Clean code architecture, data flow design, and attention to system boundaries.
2. ML/AI System Design: How you architect a complex system with multiple ML components working together.
3. Technical Depth: Demonstrated knowledge in your implemented component, whether it
involves traditional ML, NLP techniques, or newer approaches
4. Production Thinking: Considerations for scalability, monitoring, and failure modes.
5. Critical Evaluation: How you analyze potential weaknesses and propose mitigations

Most importantly, focus on quality over quantity - a well-designed smaller component is better than a rushed full system.


### Initial thoughts

The AI interviewer pipleine is quite complex, but let's me take a step back and analyse what Prolific is asking for at its core, ground this in a simpler business context:

- Why: Prolific is a platform that connects researchers with high-quality, vetted participants for AI evaluation tasks. Their entire business model rests on the trustworthiness and accuracy of their participants pool.
- The problem: They need to verify that participants who claim to have specific, often technical expertise (e.g., Python expert, Java expert, etc.) actually have that expertise. Manual verification is time-consuming and error-prone. They need a way to efficiently and accurately verify participant expertise. So ultimately, the question is how can they algorithmically trust that a human knows what they say they know — at scale — and with minimal human supervision?

More specifically,
- Epistemic uncertainty (how sure are we about this person's expertise?) -> This is the core question that we need to answer, how do we estimate expertise confidence without a labelled dataset?
- Signal extraction (how to extract evidence of competence from unstructured dialogue)->
- Cost-efficiency (how many turns / dollars per verification) -> The challenge is information efficiency: how to maximize information gain per question. Each participant can’t be grilled for 30 minutes — the system must make reliable judgments in 5–10 turns.
- Robustness to deception or overclaiming -> People express knowledge in narrative, idiosyncratic ways. You’re verifying skill through natural language, which is noisy and easily confounded by verbal fluency.
- Consistency across diverse domains and respondents
- Scalability: It’s not one interview — it’s hundreds or thousands per day, across domains.-> The challenge is to design a modular, auditable pipeline (not a monolith) that can scale and evolve.



### My proposition
The core challenge is to transform free-form human responses into structured, evidence-based expertise assessments under time and resource constraints.
One of the core problem I think is, Given uncertain beliefs about a participant’s skill claims, how can the interviewer adapt its next question to maximize evidence of true expertise while minimizing wasted turns?
My prototype demonstrates a conversation flow manager that adaptively selects the most informative questions for verifying a participant’s claimed expertise. It balances exploration and exploitation under a limited interaction budget, updating probabilistic beliefs about expertise after each answer

Outline:
- Inputs: skill claims from CVs
- Core loop: ask → grade → update belief → next question
- Outputs: verification scores per skill
- Metrics: #skills verified per turn, confidence gain per cost


## MVP contract:


Components:

1. Data Ingestion Service -> Credential Analysis Component:

    ```mermaid
    flowchart LR
    A[Raw Sources CV / LinkedIn / Scholar] --> B[Extracted Entities roles, skills, pubs]
    B --> C[Normalize\n- canonical skill names\n- org name mapping\n- date parsing]
    C --> D[Record-level Merge - roles - skills - publications]
    D --> E[Confidence Scoring - source weights - recency - agreement]
    E --> F[Unified Expertise Profile + provenance per field]
    ```

    - High level overview: Ingest → Redact → Extract → Normalize → Confidence & Evidence → Read.
    - An API endpoint that ingests participant credentials (CVs, LinkedIn profiles, link to Google Scholar)
    - Store raw files in a blob storage like S3 or GCP storage
    - Parse the raw files to extract key skills and expertise claims. -> There are different ways to do this. But for now, I will use a simple approach of extracting the text from the files and using a simple LLM with function calling or JSON mode, to extracts structured information (work experience, education, skills, etc.) -> we can extend this to Knowledge Graphs / or replace with a finetunied NER model for better accuracy.
    - PII redaction: for PII redaction, we can use Micorsoft Presidio or our own custom PII redaction model.
    - Skill normaliser: Takes the extracted raw skills and normalises them to a standard format (e.g., "pyTorch","PyTorch Lightning") -> map them to a canonical entity in a central skills Taxonomy Database. This should be done using embeddings and nearest neighbour search.
    - Output: A structured JSON object representing the participant's "claimed expertise profile".

    ```json
    {
  "skill_canonical": "pytorch",
  "raw_aliases": ["PyTorch Lightning", "pyTorch"],
  "level_claimed": "advanced",
  "experience_years_claimed": 3,
  "last_used_year": 2025,
  "evidence": [
    {"source":"cv_upload","span":"...","confidence":0.86}, // This can be weighted by recentness and relevance
    {"source":"linkedin_upload","span":"...","confidence":0.74}
  ],
  "normalization": {
    "taxonomy_id":"ML/Frameworks/PyTorch",
    "method":"embedding+synonym",
    "version":"v1",
    "confidence":0.9
  }
    }
    ```
    - Storage: Store the structured JSON object in a relational database like PostgreSQL.
    - Technical implementation:
        - JD, CV, LI -> trigger an API endpoint -> store raw files -> message queue (e.g., SQS) -> processing pipeline -> structured JSON object -> store in database.
        - API schema:
            - POST /v1/profiles/ingest
                - headers:
                    - Idempotency-Key: <unique request id>
                - content-type: multipart/form-data
                - body:
                    - cv: file (required, max 10MB)
                    - cv_content_type: string (optional, e.g. "application/pdf")
                    - linkedin_url: string (optional)
                    - google_scholar_url: string (optional)
                - response: {profile_id: str}
            - GET /v1/profiles/{id}
                - params: {id: str}
                - response: {
                    profile_id: str,
                    status: str,
                    profile: {
                        "top_skills": [
                            {
                                "skill": str,
                                "level_estimate": str,
                                "confidence": float,
                                "evidence_sources": int,
                                "last_used": int
                            }
                        ],
                        "gaps": [str]
                    },
                    created_at: timestamp
                }
            - GET /v1/profiles/{id}/history
                - params: {id: str}
                - response: {
                    profile_id: str,
                    history: [
                        {
                            timestamp: str,
                            action: str,
                            details: JSON,
                            actor: str
                        }
                    ]
                }
        - Message queue:
            - SQS queue:
                - name: prolific-interview-ingestion-queue
                - message body: {
                    "cv": "base64_encoded_cv",
                    "linkedin": "base64_encoded_linkedin",
                    "google_scholar": "base64_encoded_google_scholar"
                }
        - Database:
            - PostgreSQL:
                - table: prolific_interview_profiles
                - columns: {
                    "profile_id": UUID,
                    "created_at": timestamp,
                    "user_id": UUID,
                    "status": enum("pending", "verified", "rejected"),
                    "reason": text,
                    "profile": JSON
                }
        - Monitoring:
            - Prometheus:
                - metrics: {
                    "ingestion_errors": count,
                    "ingestion_successes": count,
                    "ingestion_time": duration
                }

2. AI Interviewer Component:
