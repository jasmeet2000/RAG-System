"""
Prompt Templates — Centralized repository for all LLM prompts.

=== WHY THIS FILE EXISTS ===
Hardcoding prompt strings inside API endpoints is an anti-pattern.
Prompts are code. They need to be versioned, tested, and managed centrally.

If a model starts hallucinating, the prompt is the first place you check.
By keeping templates here, we can easily swap them out for different models
(e.g., Llama 3 might need different instructions than Mistral).

=== INDUSTRY BEST PRACTICES ===
1. Strict Boundaries: The prompt explicitly tells the LLM where the context
   begins and ends using XML-style tags (<context>...</context>). This prevents
   the LLM from confusing user input with retrieved context (Prompt Injection mitigation).
2. Explicit Ignorance: We forcefully instruct the LLM to say "I don't know" 
   rather than guessing if the answer isn't in the context.
"""

from string import Template

# The System Prompt defines the LLM's persona and absolute rules.
RAG_SYSTEM_PROMPT = """You are an expert, truthful AI assistant.
Your primary directive is to answer the user's question using ONLY the provided context.

RULES:
1. If the answer is not contained within the context, you MUST say "I cannot answer this based on the provided documents." Do not guess.
2. Do not use your pre-trained knowledge to answer the question.
3. If the context contains conflicting information, state the conflict.
4. Keep your answer concise and well-formatted using Markdown.
5. Use citations if possible based on the source documents provided.
"""

# The User Prompt Template combines the User Query and the Retrieved Context.
# We use Python's built-in string.Template for safe substitution.
RAG_USER_PROMPT_TEMPLATE = Template("""
Please answer the following question based strictly on the provided context documents.

<context>
$context_str
</context>

Question: $query

Answer:
""")
