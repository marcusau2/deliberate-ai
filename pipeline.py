"""
LLM Pipeline for Deliberate AI
"""

import json
import logging
import threading
import concurrent.futures
import re
from typing import Optional, List, Callable
from openai import OpenAI

logger = logging.getLogger(__name__)

# Token estimation: 1 token ≈ 4 characters
TOKEN_ESTIMATE_FACTOR = 4
HARD_TOKEN_LIMIT = 120000
COMPRESSION_THRESHOLD = 15000


class Pipeline:
    def __init__(self, endpoint_url: str, model_name: str, api_key: str = "empty"):
        self.client = OpenAI(base_url=endpoint_url, api_key=api_key)
        self.model_name = model_name
        self.token_count = 0

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return len(text) // TOKEN_ESTIMATE_FACTOR

    def call_llm(
        self,
        messages: list,
        thinking: bool = False,
        temperature: float = 0.85,
        max_tokens: int = 2000,
        retry: bool = True,
        timeout: int = 600,
        raw_response: bool = False,
        stop_sequences: list = None,
    ):
        """Make LLM call with optional thinking mode and retry logic.

        Args:
            timeout: Request timeout in seconds. Default 600s (10 min) for complex tasks.
            raw_response: If True, return raw string without JSON parsing. Default False.
            stop_sequences: List of strings that stop generation when encountered. Default None.
        """
        try:
            extra_body = {}
            # Qwen3.5 requires enable_thinking in chat_template_kwargs
            extra_body["chat_template_kwargs"] = {"enable_thinking": thinking}

            # Add stop sequences if provided
            if stop_sequences:
                extra_body["stop"] = stop_sequences

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stop=stop_sequences,  # Pass stop sequences directly
                extra_body=extra_body if extra_body else None,
                timeout=timeout,
            )

            content = response.choices[0].message.content

            # Some vLLM configs return reasoning instead of content
            if content is None:
                content = getattr(response.choices[0].message, "reasoning", None)

            if content is None:
                raise ValueError("No content or reasoning in response")

            # Return raw response if requested
            if raw_response:
                return content

            # Try to parse JSON
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                if retry:
                    # Retry with stricter prompt
                    retry_messages = messages + [
                        {
                            "role": "user",
                            "content": "IMPORTANT: Return ONLY valid JSON with no additional text. The response must be parseable JSON.",
                        }
                    ]
                    return self.call_llm(
                        retry_messages, thinking, temperature, max_tokens, retry=False
                    )
                else:
                    raise ValueError("Failed to parse JSON after retry")

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def stage1_situation_extraction(
        self, input_text: str, search_context: Optional[str] = None
    ) -> dict:
        """Stage 1: Extract structured situation summary with domain context."""
        context_block = ""
        if search_context:
            context_block = f"\n\nCurrent Context (from web search):\n{search_context}"

        prompt = f"""Extract a structured situation summary from the following input:{context_block}

Input:
{input_text}

Return JSON with this exact structure:
{{
  "title": "string",
  "core_issue": "string",
  "background": "string",
  "key_stakeholders": ["string"],
  "domain": "geopolitical|interpersonal|social|financial|technical|narrative",
  "prediction_question": "string",
  "relevant_disciplines": ["list of relevant disciplines like 'climate science', 'economic policy', 'engineering', 'ethics', 'law'"],
  "typical_roles": ["list of specific role types like 'climate scientist', 'policy maker', 'industry analyst', 'NGO director'"],
  "domain_context": "string describing the domain-specific context and key tensions"
}}"""

        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(messages, thinking=False, temperature=0.7)

    def stage2_persona_generation(
        self,
        situation: dict,
        original_input: str,
        search_context: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> list:
        """Stage 2: Generate domain-specific personas concurrently with grounding.

        Creates realistic personas with specific roles, organizations, and domain expertise
        based on the situation context, following multi-agent debate research best practices.

        Args:
            situation: The situation dict from Stage 1
            original_input: Full original input text for grounding
            search_context: Web search results (if available)
            progress_callback: Optional callback(persona) for real-time UI updates

        Returns:
            List of 12 domain-specific personas with grounded positions
        """
        domain = situation.get("domain", "social")
        disciplines = situation.get("relevant_disciplines", [])
        role_types = situation.get("typical_roles", [])
        domain_context = situation.get("domain_context", "")

        # Define approach archetypes (how they think/argue)
        approaches = [
            "Advocate",  # Strongly supports a position
            "Critic",  # Questions assumptions and risks
            "Compromiser",  # Seeks middle ground
            "Idealist",  # Focuses on principles and values
            "Pragmatist",  # Focuses on feasibility and costs
            "Radical",  # Pushes for transformative change
            "Moderate",  # Cautious, incremental approach
            "Skeptic",  # Doubts feasibility or motives
            "Visionary",  # Long-term, big-picture thinking
            "Traditionalist",  # Prefers established methods
            "Reformer",  # Wants systematic improvement
            "Conservative",  # Risk-averse, status quo
        ]

        # If we don't have role types from Stage 1, create domain-specific defaults
        if not role_types:
            if domain == "geopolitical":
                role_types = [
                    "policy analyst",
                    "diplomat",
                    "NGO director",
                    "industry lobbyist",
                    "academic researcher",
                    "community advocate",
                ]
            elif domain == "financial":
                role_types = [
                    "portfolio manager",
                    "risk analyst",
                    "regulatory compliance officer",
                    "investment strategist",
                    "economist",
                    "consumer advocate",
                ]
            elif domain == "technical":
                role_types = [
                    "senior engineer",
                    "research scientist",
                    "product manager",
                    "security expert",
                    "open source contributor",
                    "enterprise architect",
                ]
            elif domain == "interpersonal":
                role_types = [
                    "family therapist",
                    "mediator",
                    "psychologist",
                    "cultural advisor",
                    "conflict resolution specialist",
                    "community leader",
                ]
            else:
                role_types = [
                    "subject matter expert",
                    "stakeholder representative",
                    "industry analyst",
                    "policy observer",
                    "academic researcher",
                    "practitioner",
                ]

        # If we don't have disciplines, create generic ones
        if not disciplines:
            disciplines = [
                "domain expertise",
                "policy analysis",
                "economic implications",
                "ethical considerations",
            ]

        # Truncate original input for prompt
        input_truncated = (
            original_input[:5000] if len(original_input) > 5000 else original_input
        )

        # Prepare search context block
        search_block = ""
        if search_context:
            search_block = f"\n\nWEB SEARCH CONTEXT (reference if relevant):\n{search_context[:2000]}"

        # STEP 1: Generate 12 unique names with diverse origins and unique last names
        # This ensures no duplicate last names across all personas
        name_generation_prompt = f"""Generate exactly 12 UNIQUE names with diverse cultural origins.

CRITICAL REQUIREMENTS:
1. Each name must have a UNIQUE LAST NAME - NO DUPLICATES ALLOWED
2. Include diverse origins: Middle Eastern, African, South Asian, East Asian, Eastern European, Latin American, Western European, Anglo-American (roughly 2 per region)
3. Names should be realistic and authentic to their cultural origin
4. Return ONLY JSON array with this exact structure:

[
  {{"region": "Middle Eastern", "first_name": "Name", "last_name": "UniqueLastName"}},
  {{"region": "African", "first_name": "Name", "last_name": "UniqueLastName"}},
  ... (12 total, each with unique last name)
]

Ensure all 12 last names are completely different from each other."""

        try:
            name_result = self.call_llm(
                [{"role": "user", "content": name_generation_prompt}],
                thinking=False,
                temperature=0.8,
                max_tokens=500,
                retry=True,
            )

            # Parse the names
            if isinstance(name_result, list) and len(name_result) == 12:
                name_pool = name_result
                # Validate unique last names
                last_names = [n.get("last_name", "") for n in name_result]
                if len(last_names) == len(set(last_names)):
                    # All last names are unique - good!
                    pass
                else:
                    # Duplicate last names found - regenerate with stricter constraints
                    name_generation_prompt += "\n\n⚠️ WARNING: You have duplicate last names. Regenerate with 12 COMPLETELY UNIQUE last names."
                    name_result = self.call_llm(
                        [{"role": "user", "content": name_generation_prompt}],
                        thinking=False,
                        temperature=0.9,
                        max_tokens=500,
                        retry=False,
                    )
                    name_pool = name_result if isinstance(name_result, list) else []
            else:
                name_pool = []
        except Exception as e:
            logger.warning(f"Name generation failed: {e}. Using fallback names.")
            name_pool = []

        # Fallback names if generation failed (ensures unique last names)
        if len(name_pool) < 12:
            name_pool = [
                {
                    "region": "Middle Eastern",
                    "first_name": "Layla",
                    "last_name": "Hassan",
                },
                {
                    "region": "Middle Eastern",
                    "first_name": "Omar",
                    "last_name": "Farooq",
                },
                {"region": "African", "first_name": "Kwame", "last_name": "Mensah"},
                {"region": "African", "first_name": "Amara", "last_name": "Nwosu"},
                {"region": "South Asian", "first_name": "Priya", "last_name": "Sharma"},
                {"region": "South Asian", "first_name": "Arjun", "last_name": "Patel"},
                {"region": "East Asian", "first_name": "Wei", "last_name": "Zhang"},
                {"region": "East Asian", "first_name": "Yuki", "last_name": "Tanaka"},
                {
                    "region": "Eastern European",
                    "first_name": "Natasha",
                    "last_name": "Volkov",
                },
                {
                    "region": "Eastern European",
                    "first_name": "Viktor",
                    "last_name": "Novak",
                },
                {
                    "region": "Latin American",
                    "first_name": "Mateo",
                    "last_name": "Rivera",
                },
                {
                    "region": "Latin American",
                    "first_name": "Isabella",
                    "last_name": "Castillo",
                },
            ]

        # Ensure we have exactly 12 names
        while len(name_pool) < 12:
            name_pool.append(
                {
                    "region": "Western European",
                    "first_name": "Default",
                    "last_name": f"Person{len(name_pool)}",
                }
            )

        # STEP 2: Create role-approach pairings for 12 personas
        role_approach_pairs = []
        for i in range(12):
            role = role_types[i % len(role_types)]
            approach = approaches[i % len(approaches)]
            role_approach_pairs.append((role, approach))

        def generate_single_persona(role_type, approach, assigned_name):
            """Generate a single domain-specific persona with assigned name and role."""
            prompt = f"""Create a domain-specific persona for this situation:

SITUATION TITLE: {situation.get("title")}
CORE ISSUE: {situation.get("core_issue")}
DOMAIN: {domain}
DOMAIN CONTEXT: {domain_context}

RELEVANT DISCIPLINES: {", ".join(disciplines)}
STAKEHOLDER ROLES: {", ".join(role_types)}

YOUR PERSONA TO CREATE:
- Assigned Name: {assigned_name["first_name"]} {assigned_name["last_name"]} (MUST use this exact name)
- Region: {assigned_name["region"]}
- Role Type: {role_type}
- Approach Lens: {approach} (how this persona thinks and argues)

ORIGINAL INPUT (MUST reference specific details):
{input_truncated}{search_block}

DIVERSITY MANDATE - CRITICAL:
You are creating ONE of 12 personas. Each of the 12 personas must be UNIQUE and DISTINCT.

DIVERSITY REQUIREMENTS:
- Names must represent at least 6 different cultural/ethnic backgrounds across the 12 personas
- NO repeated first names across any of the 12 personas
- NO repeated last names across any of the 12 personas
- Avoid common Western names (John, Jane, Michael, Sarah, David, etc.)
- Include diverse naming conventions from multiple global regions
- Each persona's name must be genuinely unique and not echo or resemble other personas
- Names should reflect authentic cultural diversity, not variations of similar names

CRITICAL REQUIREMENTS:
1. Create a SPECIFIC, REALISTIC persona with:
   - Use the ASSIGNED name: {assigned_name["first_name"]} {assigned_name["last_name"]} (from {assigned_name["region"]} region)
   - A specific job title (e.g., "Senior Policy Analyst", "Director of Renewable Energy")
   - A specific organization (e.g., "EPA", "World Bank", "Tesla", "Greenpeace") - vary organizations
   - Years of experience and relevant background

2. Worldview must be shaped by:
   - Their role's incentives and constraints
   - Their disciplinary expertise
   - Their organization's mission and pressures

3. Initial position MUST:
   - Reference SPECIFIC details from the original input above
   - NOT be a generic statement
   - Show how their role and approach shape their view
   - Include reasoning based on their expertise

4. Likely bias should reflect:
   - Institutional pressures they face
   - Disciplinary blind spots
   - Stakeholder interests they represent

BEFORE finalizing, verify:
✓ My name is unique and culturally distinct from all other personas
✓ My name does not resemble or echo other personas (avoid variations like "Elena Petrova", "Elena Petrov", "Elena Petrova-Smith")
✓ My organization is specific and different from other personas
✓ My background (education, geography, career) is distinct
✓ My perspective is shaped by my specific role and approach
✓ I reference specific details from the input, not generic statements

If any of these are NOT true, regenerate your persona with different characteristics.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "id": "p_X",
  "name": "{assigned_name["first_name"]} {assigned_name["last_name"]}",
  "role_title": "Specific job title",
  "organization": "Specific organization",
  "role_type": "{role_type}",
  "approach": "{approach}",
  "years_experience": "number",
  "background": "Detailed domain-specific background and expertise",
  "worldview": "How their role/discipline shapes their perspective",
  "likely_bias": "Incentives/constraints from their position",
  "initial_position": "Specific stance with reasoning grounded in input details"
}}"""

            messages = [{"role": "user", "content": prompt}]

            # Try multiple times with increasing strictness
            persona = None
            for attempt in range(3):
                try:
                    persona = self.call_llm(
                        messages,
                        thinking=False,
                        temperature=0.85,
                        max_tokens=800,
                        retry=(attempt < 2),
                    )
                    if persona and isinstance(persona, dict):
                        # Ensure all required fields exist
                        required_fields = [
                            "id",
                            "name",
                            "role_title",
                            "organization",
                            "role_type",
                            "approach",
                            "years_experience",
                            "background",
                            "worldview",
                            "likely_bias",
                            "initial_position",
                        ]
                        for field in required_fields:
                            if field not in persona:
                                persona[field] = ""

                        # Ensure name matches assigned name
                        persona["name"] = (
                            f"{assigned_name['first_name']} {assigned_name['last_name']}"
                        )

                        # Generate ID if missing
                        if not persona.get("id"):
                            persona["id"] = (
                                f"p_{role_type.replace(' ', '_')}_{approach.lower()}"
                            )

                        return persona
                except Exception as e:
                    logger.warning(
                        f"Persona generation attempt {attempt + 1} failed: {e}"
                    )
                    if attempt < 2:
                        messages = [
                            {
                                "role": "user",
                                "content": prompt
                                + "\n\nCRITICAL: Return ONLY valid JSON, nothing else. No markdown, no explanations.",
                            }
                        ]

            # Fallback persona with assigned name
            return {
                "id": f"p_{role_type.replace(' ', '_')}_{approach.lower()}",
                "name": f"{assigned_name['first_name']} {assigned_name['last_name']}",
                "role_title": role_type.title(),
                "organization": "Unknown",
                "role_type": role_type,
                "approach": approach,
                "years_experience": "0",
                "background": f"{role_type} with {approach} approach",
                "worldview": "Generic perspective",
                "likely_bias": "None specified",
                "initial_position": "Position pending - see situation context",
            }

        # Generate personas concurrently with assigned names
        personas = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            futures = [
                executor.submit(generate_single_persona, role, approach, name_pool[i])
                for i, (role, approach) in enumerate(role_approach_pairs)
            ]

            for future in concurrent.futures.as_completed(futures):
                try:
                    persona = future.result()
                    personas.append(persona)
                    if progress_callback:
                        progress_callback(persona)
                except Exception as e:
                    logger.error(f"Persona generation failed: {e}")
                    # Add fallback persona
                    personas.append(
                        {
                            "id": f"p_fallback_{len(personas)}",
                            "name": f"{name_pool[len(personas)]['first_name']} {name_pool[len(personas)]['last_name']}",
                            "role_title": "Unknown",
                            "organization": "Unknown",
                            "role_type": "Unknown",
                            "approach": "Unknown",
                            "years_experience": "0",
                            "background": "Generation failed",
                            "worldview": "Unknown",
                            "likely_bias": "Unknown",
                            "initial_position": "See situation context",
                        }
                    )

        # Ensure we have exactly 12 personas
        while len(personas) < 12:
            personas.append(
                {
                    "id": f"p_missing_{len(personas)}",
                    "name": "Missing Persona",
                    "role_title": "Unknown",
                    "organization": "Unknown",
                    "role_type": "Unknown",
                    "approach": "Unknown",
                    "years_experience": "0",
                    "background": "Missing",
                    "worldview": "Unknown",
                    "likely_bias": "Unknown",
                    "initial_position": "See situation context",
                }
            )

        # Sort by ID for consistency
        personas.sort(key=lambda p: p.get("id", ""))

        # POST-GENERATION VALIDATION: Check for duplicate last names
        last_names = []
        for persona in personas:
            name_parts = persona.get("name", "").split()
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
                last_names.append(last_name)

        # Flag any duplicates
        from collections import Counter

        last_name_counts = Counter(last_names)
        duplicates = [ln for ln, count in last_name_counts.items() if count > 1]

        if duplicates:
            logger.warning(
                f"WARNING: Duplicate last names found: {duplicates}. This should not happen."
            )
            # Note: In production, you could regenerate these personas, but for now we'll log the warning

        return personas[:12]

    def ensure_distinct_personas(self, personas: list) -> list:
        """Ensure all personas have distinct names and organizations.

        If duplicates found, regenerate with stricter uniqueness requirements.
        """
        names = [p.get("name", "") for p in personas]
        organizations = [p.get("organization", "") for p in personas]

        # Check for duplicates
        name_duplicates = len(names) != len(set(names))
        org_duplicates = len(organizations) != len(set(organizations))

        if not name_duplicates and not org_duplicates:
            return personas

        # Found duplicates - need to fix them
        logger.info(f"Found duplicate names: {name_duplicates}, orgs: {org_duplicates}")

        # Track used names and organizations
        used_names = set()
        used_orgs = set()

        # Diversity pools for regeneration
        first_names = [
            "Alex",
            "Jordan",
            "Taylor",
            "Morgan",
            "Casey",
            "Riley",
            "Jamie",
            "Quinn",
            "Avery",
            "Parker",
            "Reese",
            "Dakota",
            "Skyler",
            "Emerson",
            "River",
            "Phoenix",
            "Rowan",
            "Sage",
            "Finley",
            "Kai",
        ]
        last_names = [
            "Chen",
            "Rodriguez",
            "Patel",
            "Johnson",
            "Kim",
            "Okonkwo",
            "Mueller",
            "Santos",
            "Nakamura",
            "Kowalski",
            "Nguyen",
            "Silva",
            "Cohen",
            "O'Brien",
            "Patel",
            "Garcia",
            "Williams",
            "Zhang",
            "Thompson",
            "Anderson",
        ]
        organizations_pool = [
            "EPA",
            "World Bank",
            "Tesla",
            "Greenpeace",
            "Brookings Institution",
            "Cato Institute",
            "MIT",
            "Stanford",
            "UN Development Programme",
            "IMF",
            "Goldman Sachs",
            "Siemens",
            "Amazon Web Services",
            "Mayo Clinic",
            "Red Cross",
            "Amnesty International",
            "Heritage Foundation",
            "Rand Corporation",
            "OECD",
            "Nature Conservancy",
        ]

        for i, persona in enumerate(personas):
            # Fix duplicate names
            current_name = persona.get("name", "")
            name_parts = current_name.split()

            if current_name in used_names or len(name_parts) < 2:
                # Generate unique name
                first = first_names[i % len(first_names)]
                last = last_names[i % len(last_names)]
                # Ensure uniqueness
                while f"{first} {last}" in used_names:
                    i += 1
                    first = first_names[i % len(first_names)]
                    last = last_names[i % len(last_names)]
                persona["name"] = f"{first} {last}"

            used_names.add(persona["name"])

            # Fix duplicate organizations
            current_org = persona.get("organization", "")
            if current_org in used_orgs or current_org == "Unknown":
                org = organizations_pool[i % len(organizations_pool)]
                # Ensure uniqueness
                while org in used_orgs:
                    i += 1
                    org = organizations_pool[i % len(organizations_pool)]
                persona["organization"] = org

            used_orgs.add(persona["organization"])

        return personas

    def stage0_initial_positions(
        self,
        personas: list,
        situation: dict,
        original_input: str,
        search_context: Optional[str] = None,
    ) -> list:
        """Stage 0: Generate detailed initial position statements before simulation."""
        persona_ref = "\n".join(
            [
                f"{p['id']}: {p['name']} - {p.get('role_title', 'Unknown')} ({p.get('approach', 'Unknown')}) - {p['worldview']}"
                for p in personas
            ]
        )

        # Truncate original input to keep within token limits
        input_truncated = (
            original_input[:8000] if len(original_input) > 8000 else original_input
        )

        # Prepare search context block
        search_block = ""
        if search_context:
            search_block = (
                f"\n\nWEB SEARCH CONTEXT (use for factual grounding):\n{search_context}"
            )

        prompt = f"""Situation: {situation.get("title")} - {situation.get("core_issue")}

ORIGINAL INPUT (ground your position in THESE SPECIFIC DETAILS):
{input_truncated}{search_block}

Persona Reference:
{persona_ref}

Each persona delivers their DETAILED INITIAL POSITION before any interaction occurs.
Provide comprehensive reasoning, values, and expectations.

CRITICAL GROUNDING REQUIREMENTS:
- Your position MUST directly engage with SPECIFIC details from the original input above
- Reference specific proposals, numbers, stakeholders, or arguments from the input text
- Do NOT generate generic positions - react to the ACTUAL content described
- Explain how your background/worldview shapes your reaction to the SPECIFIC situation
- If web search context is provided, you may reference specific facts from it
- Your position must show engagement with the ACTUAL CONTENT, not just the topic category

Return JSON with this exact structure for each persona:
[
  {{
    "persona_id": "string",
    "position": "string",
    "reasoning": "string",
    "values": ["string"],
    "expectations": "string"
  }}
]

Keep each response under 250 tokens."""

        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(
            messages, thinking=False, temperature=0.85, max_tokens=5000
        )

    def stage3_simulation_round(
        self,
        personas: list,
        situation: dict,
        round_history: list,
        current_round: int,
        total_rounds: int,
        include_initial_positions: bool = False,
        initial_positions: Optional[list] = None,
        search_context: Optional[str] = None,
    ) -> list:
        """Stage 3: Run a single simulation round with all personas."""
        persona_ref = "\n".join(
            [
                f"{p['id']}: {p.get('role_title', 'Unknown')} ({p.get('approach', 'Unknown')}) - {p['worldview']}"
                for p in personas
            ]
        )

        history_text = ""
        if round_history:
            history_text = "\n\nPrevious Rounds:\n" + "\n".join(
                [
                    f"Round {h['round']}: {h['dominant_positions']} | Shifts: {h['notable_shifts']}"
                    for h in round_history
                ]
            )

        initial_block = ""
        if include_initial_positions and initial_positions:
            initial_block = "\n\nInitial Positions (Round 0):\n" + "\n".join(
                [
                    f"{ip['persona_id']}: {ip['position'][:100]}..."
                    for ip in initial_positions
                ]
            )

        # Prepare search context block
        search_block = ""
        if search_context:
            search_block = (
                "\n\nWEB SEARCH CONTEXT (reference if relevant):\n" + search_context
            )

        prompt = f"""Situation: {situation.get("title")} - {situation.get("core_issue")}

Persona Reference (ID: Role - Approach - Worldview):
{persona_ref}{initial_block}{search_block}

Round {current_round} of {total_rounds}
{history_text}

All personas respond to the current state of the situation. Each should express their position, reaction to others, and any position shifts. Provide detailed reasoning.

CRITICAL REQUIREMENTS:
- Ground your position in the SPECIFIC details from the original input and situation
- You may reference facts from the web search context if relevant
- React to other personas' positions and explain your reasoning
- Provide detailed reasoning for any position shifts

Return a JSON array with this exact structure for each persona:
[
  {{
    "persona_id": "string",
    "position": "string",
    "reaction": "string",
    "shift": "none|softened|hardened|changed",
    "influenced_by": ["persona_id"]
  }}
]

Keep each response under 250 tokens."""

        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(
            messages, thinking=False, temperature=0.85, max_tokens=4000
        )

    def stage3_sequential_round(
        self,
        personas: list,
        situation: dict,
        round_history: list,
        current_round: int,
        total_rounds: int,
        include_initial_positions: bool = False,
        initial_positions: Optional[list] = None,
        search_context: Optional[str] = None,
    ) -> tuple:
        """Stage 3: Run a sequential round where personas respond one-by-one.

        Each persona sees all previous responses in the current round before responding.
        Returns (round_responses, converged) where converged indicates if debate stabilized.
        """
        persona_ref = "\n".join(
            [
                f"{p['id']}: {p.get('role_title', 'Unknown')} ({p.get('approach', 'Unknown')}) - {p['worldview']}"
                for p in personas
            ]
        )

        history_text = ""
        if round_history:
            history_text = "\n\nPrevious Rounds:\n" + "\n".join(
                [
                    f"Round {h['round']}: {h['dominant_positions']} | Shifts: {h['notable_shifts']}"
                    for h in round_history
                ]
            )

        initial_block = ""
        if include_initial_positions and initial_positions:
            initial_block = "\n\nInitial Positions (Round 0):\n" + "\n".join(
                [
                    f"{ip['persona_id']}: {ip['position'][:100]}..."
                    for ip in initial_positions
                ]
            )

        # Prepare search context block
        search_block = ""
        if search_context:
            search_block = (
                "\n\nWEB SEARCH CONTEXT (reference if relevant):\n" + search_context
            )

        # Collect all responses sequentially
        sequential_responses = []
        previous_response_summary = ""

        for i, persona in enumerate(personas):
            # Build context with previous responses in this round
            current_round_context = ""
            if previous_response_summary:
                current_round_context = (
                    f"\n\nResponses so far in this round:\n{previous_response_summary}"
                )

            prompt = f"""You are participating in a structured debate. Return ONLY valid JSON - no other text.

Situation: {situation.get("title")} - {situation.get("core_issue")}

Your Role: {persona["name"]}
Role Title: {persona.get("role_title", "Unknown")}
Approach: {persona.get("approach", "Unknown")}
Worldview: {persona.get("worldview", "")}

{persona_ref}

{initial_block}

{search_block}

{current_round_context}

{history_text}

Instructions:
1. Respond as your persona would
2. Reference specific details from the situation and previous responses
3. Indicate if your position has shifted based on what others said
4. Return ONLY a JSON object with this exact structure:

{{
  "persona_id": "{persona["id"]}",
  "position": "Your detailed position statement",
  "reaction": "Your reaction to other personas' positions",
  "shift": "none",
  "influenced_by": []
}}

Where "shift" must be one of: "none", "softened", "hardened", or "changed"

CRITICAL: Return ONLY the JSON object. No markdown, no explanations, no extra text."""

            messages = [{"role": "user", "content": prompt}]

            # Try to parse JSON with retry logic
            response = None
            for attempt in range(3):
                try:
                    result = self.call_llm(
                        messages,
                        thinking=False,
                        temperature=0.85,
                        max_tokens=600,
                        retry=(attempt < 2),
                    )

                    # Ensure it's a dict with required fields
                    if isinstance(result, dict):
                        # Validate required fields
                        required = [
                            "persona_id",
                            "position",
                            "reaction",
                            "shift",
                            "influenced_by",
                        ]
                        if all(field in result for field in required):
                            # Ensure shift is valid
                            if result["shift"] not in [
                                "none",
                                "softened",
                                "hardened",
                                "changed",
                            ]:
                                result["shift"] = "none"
                            if not isinstance(result["influenced_by"], list):
                                result["influenced_by"] = []
                            response = result
                            break
                except Exception as e:
                    if attempt < 2:
                        messages = [
                            {
                                "role": "user",
                                "content": 'CRITICAL ERROR: Return ONLY valid JSON. No text before or after. Use this exact structure:\n{\n  "persona_id": "string",\n  "position": "string",\n  "reaction": "string",\n  "shift": "none|softened|hardened|changed",\n  "influenced_by": ["string"]\n}',
                            }
                        ]

            if response is None:
                # Fallback response
                response = {
                    "persona_id": persona["id"],
                    "position": "Position pending due to parsing error",
                    "reaction": "Unable to respond properly",
                    "shift": "none",
                    "influenced_by": [],
                }

            sequential_responses.append(response)

            # Build summary for next persona
            previous_response_summary += f"\n{persona['id']} ({persona.get('approach', 'Unknown')}): {response.get('position', '')[:150]}... [Shift: {response.get('shift', 'none')}]"

        # Check for early convergence: all personas have shift="none"
        all_none_shift = all(
            resp.get("shift", "none") == "none" for resp in sequential_responses
        )

        # Also check if previous round had all none shifts (for 2 consecutive rounds)
        converged = False
        if all_none_shift and round_history:
            prev_round = round_history[-1]
            prev_shifts = prev_round.get("notable_shifts", [])
            if not prev_shifts or all("none" in str(s).lower() for s in prev_shifts):
                converged = True

        return sequential_responses, converged

    def calculate_confidence_score(
        self, persona: dict, round_history: list, all_responses: list = None
    ) -> dict:
        """
        Calculate confidence score from multiple signals.

        Args:
            persona: Persona dict with position, shift, etc.
            round_history: List of previous round compressions
            all_responses: All responses from current round (for agreement calculation)

        Returns:
            {
                "confidence_score": 0-100,
                "confidence_factors": {
                    "position_stability": 0-100,
                    "reasoning_depth": 0-100,
                    "agreement_level": 0-100,
                    "evidence_citations": 0-100,
                    "uncertainty_language": 0-100
                }
            }
        """
        position = persona.get("position", "")

        # Signal 1: Position Stability (30% weight)
        stability_score = self._calculate_position_stability(persona, round_history)

        # Signal 2: Reasoning Depth (20% weight)
        reasoning_score = self._calculate_reasoning_depth(position)

        # Signal 3: Agreement Level (20% weight)
        agreement_score = (
            self._calculate_agreement_level(persona, all_responses)
            if all_responses
            else 70.0
        )

        # Signal 4: Evidence Citations (20% weight)
        evidence_score = self._calculate_evidence_citations(position)

        # Signal 5: Uncertainty Language (10% weight, subtractive)
        uncertainty_penalty = self._calculate_uncertainty_language(position)

        # Calculate weighted confidence
        confidence = (
            0.3 * stability_score
            + 0.2 * reasoning_score
            + 0.2 * agreement_score
            + 0.2 * evidence_score
            - 0.1 * uncertainty_penalty
        )

        # Clamp to 0-100
        confidence = max(0, min(100, confidence))

        return {
            "confidence_score": round(confidence, 1),
            "confidence_factors": {
                "position_stability": round(stability_score, 1),
                "reasoning_depth": round(reasoning_score, 1),
                "agreement_level": round(agreement_score, 1),
                "evidence_citations": round(evidence_score, 1),
                "uncertainty_language": round(uncertainty_penalty, 1),
            },
        }

    def _calculate_position_stability(
        self, persona: dict, round_history: list
    ) -> float:
        """Calculate how stable the persona's position has been across rounds."""
        if not round_history:
            return 100.0  # First round, assume stable

        # Get current position
        current_position = persona.get("position", "").lower()
        shift = persona.get("shift", "none")

        # If no shift, high stability
        if shift == "none":
            return 95.0
        elif shift == "softened":
            return 70.0
        elif shift == "hardened":
            return 85.0
        elif shift == "changed":
            return 40.0

        return 75.0  # Default

    def _calculate_reasoning_depth(self, position: str) -> float:
        """Count supporting arguments, logical structure, depth of reasoning."""
        if not position:
            return 0.0

        # Count reasoning indicators
        reasoning_indicators = [
            "because",
            "therefore",
            "thus",
            "consequently",
            "as a result",
            "first",
            "second",
            "third",
            "finally",
            "moreover",
            "furthermore",
            "however",
            "although",
            "despite",
            "in addition",
            "specifically",
            "for example",
            "for instance",
            "studies show",
            "research indicates",
        ]

        position_lower = position.lower()
        count = sum(
            1 for indicator in reasoning_indicators if indicator in position_lower
        )

        # Normalize: 0-10 indicators = 0-100 score
        return min(100, count * 10)

    def _calculate_agreement_level(self, persona: dict, all_responses: list) -> float:
        """Measure alignment with other personas' positions."""
        if not all_responses or len(all_responses) < 2:
            return 70.0  # Default if insufficient data

        current_position = persona.get("position", "").lower()

        # Extract stance from current position
        current_stance = "neutral"
        if any(
            word in current_position
            for word in ["support", "favor", "advocate", "pro", "should", "must"]
        ):
            current_stance = "support"
        elif any(
            word in current_position
            for word in ["oppose", "against", "reject", "concern", "risk", "danger"]
        ):
            current_stance = "oppose"
        elif any(
            word in current_position
            for word in ["compromise", "middle", "balance", "moderate"]
        ):
            current_stance = "compromise"

        # Count alignment with other personas
        aligned_count = 0
        for response in all_responses:
            if response.get("persona_id") == persona.get("persona_id"):
                continue

            other_position = response.get("position", "").lower()
            other_stance = "neutral"
            if any(
                word in other_position
                for word in ["support", "favor", "advocate", "pro", "should", "must"]
            ):
                other_stance = "support"
            elif any(
                word in other_position
                for word in ["oppose", "against", "reject", "concern", "risk", "danger"]
            ):
                other_stance = "oppose"
            elif any(
                word in other_position
                for word in ["compromise", "middle", "balance", "moderate"]
            ):
                other_stance = "compromise"

            if current_stance == other_stance:
                aligned_count += 1

        # Calculate agreement percentage
        total_others = len(all_responses) - 1
        agreement_ratio = aligned_count / total_others if total_others > 0 else 0.5

        return agreement_ratio * 100

    def _calculate_evidence_citations(self, position: str) -> float:
        """Count specific facts, data points, statistics, references."""
        if not position:
            return 0.0

        import re

        # Pattern 1: Numbers with units/percentages
        number_patterns = [
            r"\d+%",  # percentages
            r"\d{3,}",  # large numbers
            r"\d+\.\d+",  # decimals
            r"\d{4}",  # years
        ]

        evidence_count = 0
        for pattern in number_patterns:
            evidence_count += len(re.findall(pattern, position))

        # Pattern 2: Named sources/references
        source_patterns = [
            r"according to",
            r"report",
            r"study",
            r"research",
            r"states",
            r"indicates",
            r"data shows",
            r"statistics",
            r"survey",
            r"think tank",
            r"government",
            r"agency",
        ]

        position_lower = position.lower()
        for pattern in source_patterns:
            if pattern in position_lower:
                evidence_count += 1

        # Normalize: 0-10 evidence items = 0-100 score
        return min(100, evidence_count * 10)

    def _calculate_uncertainty_language(self, position: str) -> float:
        """Detect hedging words that indicate uncertainty."""
        if not position:
            return 0.0

        uncertainty_words = [
            "might",
            "possibly",
            "perhaps",
            "uncertain",
            "could be",
            "maybe",
            "potentially",
            "speculative",
            "hypothetically",
            "presumably",
            "seems like",
            "appears to",
            "probably",
            "likely",
            "unlikely",
        ]

        position_lower = position.lower()
        count = sum(1 for word in uncertainty_words if word in position_lower)

        # Each uncertainty word adds 10 points of penalty (max 50)
        return min(50, count * 10)

    def stage4_round_compression(self, round_data: list, round_num: int) -> dict:
        """Stage 4: Compress round responses into summary."""
        round_text = json.dumps(round_data, indent=2)

        prompt = f"""Compress this round into a summary:

Round Data:
{round_text}

Return JSON with this exact structure:
{{
  "round": {round_num},
  "dominant_positions": ["string"],
  "notable_shifts": ["string"],
  "emerging_coalitions": ["string"],
  "key_exchanges": ["string"]
}}"""

        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(messages, thinking=False, temperature=0.7)

    def stage5_report_generation(
        self,
        situation: dict,
        personas: list,
        round_history: list,
        initial_positions: Optional[list] = None,
        original_input: Optional[str] = None,
    ) -> dict:
        """Stage 5: Generate final report with persona trajectory summaries and voting comparison."""
        personas_text = json.dumps(personas, indent=2)
        history_text = json.dumps(round_history, indent=2)
        initial_text = (
            json.dumps(initial_positions, indent=2) if initial_positions else "None"
        )

        # Calculate "If We Voted" result
        voting_result = self.calculate_majority_voting(personas, round_history)

        # Prepare original input block
        input_block = ""
        if original_input:
            input_block = f"""ORIGINAL USER INPUT:
{original_input}

"""

        prompt = f"""Generate a COMPREHENSIVE, DETAILED analysis report with thorough persona trajectory analysis.

{input_block}CRITICAL REQUIREMENTS:
- Each section MUST be comprehensive and detailed (minimum 200-300 words for executive_summary and predicted_outcome)
- Do NOT summarize briefly - provide complete, substantive analysis
- Include specific details, reasoning, and evidence from the simulation

Situation:
{json.dumps(situation, indent=2)}

Personas:
{personas_text}

Initial Positions (Round 0):
{initial_text}

Simulation History:
{history_text}

MAJORITY VOTING RESULT (for comparison):
{voting_result}

Return JSON with this exact structure. Each section must be comprehensive:

{{
  "question_analyzed": "Clear, professional statement of the question being analyzed. If the original input was unclear or disjointed, rephrase it to capture the core decision while maintaining accuracy. This should be the FIRST section of the report.",
  "executive_summary": "COMPREHENSIVE executive summary (300-500 words). Include: (1) Background and context of the situation, (2) Overview of the debate process and key rounds, (3) Main findings and consensus areas, (4) Key disagreements and unresolved issues, (5) Final conclusions and implications. Do not be brief - provide complete analysis.",
  "predicted_outcome": "DETAILED predicted outcome (300-400 words). Include: (1) Specific predicted outcome with timeline, (2) Multiple scenarios if applicable (best case, worst case, most likely), (3) Key factors driving the prediction, (4) Supporting evidence from the debate, (5) Alternative outcomes that were considered and rejected. Provide specific details, not vague statements.",
  "confidence": "low|medium|high",
  "confidence_reasoning": "COMPREHENSIVE reasoning (200-300 words). Explain: (1) Why this confidence level was chosen, (2) What evidence supports this confidence, (3) What uncertainties remain, (4) What factors could change the prediction, (5) How consensus strength affects confidence.",
  "faction_breakdown": [
    {{
      "group": "Clear faction name",
      "final_position": "Detailed final position statement (2-3 sentences)",
      "trajectory": "Comprehensive trajectory description (2-3 sentences) explaining how this group evolved through the debate"
    }}
  ],
  "persona_trajectories": [
    {{
      "persona_id": "string",
      "persona_name": "string",
      "initial_position": "Their initial position from Round 0",
      "final_position": "Their final position after all rounds",
      "key_shifts": ["Specific shift 1", "Specific shift 2"],
      "evolution_summary": "COMPREHENSIVE evolution summary (2-3 sentences) describing how and why this persona's position changed or remained stable throughout the debate"
    }}
  ],
  "consensus_points": ["Detailed consensus point 1 with reasoning", "Detailed consensus point 2 with reasoning", "Continue for all consensus points"],
  "persistent_disagreements": ["Detailed disagreement 1 with both sides' arguments", "Detailed disagreement 2 with both sides' arguments", "Continue for all disagreements"],
  "key_influencers": ["Persona ID and name who most influenced the debate", "Explain why they were influential"],
  "wildcard_factors": ["Specific uncertain factor 1 and its potential impact", "Specific uncertain factor 2 and its potential impact", "Continue for all wildcard factors"],
  "recommended_actions": ["Specific actionable recommendation 1 with rationale", "Specific actionable recommendation 2 with rationale", "Continue for all recommendations"],
  "if_we_voted": {{
    "majority_outcome": "Majority voting outcome with specific details",
    "vote_distribution": {{
      "group_name": "vote_count"
    }},
    "llm_synthesis_vs_voting": "COMPREHENSIVE comparison (200-300 words). Analyze: (1) How the LLM synthesis outcome compares to majority voting, (2) Whether debate added value beyond simple voting, (3) What nuances the synthesis captured that voting missed, (4) Any discrepancies between the two approaches and why they exist, (5) Implications for decision-making"
  }}
}}

IMPORTANT: Each text field must be comprehensive and detailed. Do not provide brief summaries. Provide complete, substantive analysis with specific details, reasoning, and evidence."""

        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(
            messages, thinking=False, temperature=0.6, max_tokens=20000, timeout=900
        )

        # Calculate "If We Voted" result
        voting_result = self.calculate_majority_voting(personas, round_history)

        prompt = f"""Generate a COMPREHENSIVE, DETAILED analysis report with thorough persona trajectory analysis.

CRITICAL REQUIREMENTS:
- Each section MUST be comprehensive and detailed (minimum 200-300 words for executive_summary and predicted_outcome)
- Do NOT summarize briefly - provide complete, substantive analysis
- Include specific details, reasoning, and evidence from the simulation

Situation:
{json.dumps(situation, indent=2)}

Personas:
{personas_text}

Initial Positions (Round 0):
{initial_text}

Simulation History:
{history_text}

MAJORITY VOTING RESULT (for comparison):
{voting_result}

Return JSON with this exact structure. Each section must be comprehensive:

{{
  "executive_summary": "COMPREHENSIVE executive summary (300-500 words). Include: (1) Background and context of the situation, (2) Overview of the debate process and key rounds, (3) Main findings and consensus areas, (4) Key disagreements and unresolved issues, (5) Final conclusions and implications. Do not be brief - provide complete analysis.",
  "predicted_outcome": "DETAILED predicted outcome (300-400 words). Include: (1) Specific predicted outcome with timeline, (2) Multiple scenarios if applicable (best case, worst case, most likely), (3) Key factors driving the prediction, (4) Supporting evidence from the debate, (5) Alternative outcomes that were considered and rejected. Provide specific details, not vague statements.",
  "confidence": "low|medium|high",
  "confidence_reasoning": "COMPREHENSIVE reasoning (200-300 words). Explain: (1) Why this confidence level was chosen, (2) What evidence supports this confidence, (3) What uncertainties remain, (4) What factors could change the prediction, (5) How consensus strength affects confidence.",
  "faction_breakdown": [
    {{
      "group": "Clear faction name",
      "final_position": "Detailed final position statement (2-3 sentences)",
      "trajectory": "Comprehensive trajectory description (2-3 sentences) explaining how this group evolved through the debate"
    }}
  ],
  "persona_trajectories": [
    {{
      "persona_id": "string",
      "persona_name": "string",
      "initial_position": "Their initial position from Round 0",
      "final_position": "Their final position after all rounds",
      "key_shifts": ["Specific shift 1", "Specific shift 2"],
      "evolution_summary": "COMPREHENSIVE evolution summary (2-3 sentences) describing how and why this persona's position changed or remained stable throughout the debate"
    }}
  ],
  "consensus_points": ["Detailed consensus point 1 with reasoning", "Detailed consensus point 2 with reasoning", "Continue for all consensus points"],
  "persistent_disagreements": ["Detailed disagreement 1 with both sides' arguments", "Detailed disagreement 2 with both sides' arguments", "Continue for all disagreements"],
  "key_influencers": ["Persona ID and name who most influenced the debate", "Explain why they were influential"],
  "wildcard_factors": ["Specific uncertain factor 1 and its potential impact", "Specific uncertain factor 2 and its potential impact", "Continue for all wildcard factors"],
  "recommended_actions": ["Specific actionable recommendation 1 with rationale", "Specific actionable recommendation 2 with rationale", "Continue for all recommendations"],
  "if_we_voted": {{
    "majority_outcome": "Majority voting outcome with specific details",
    "vote_distribution": {{
      "support": "count",
      "oppose": "count",
      "compromise": "count"
    }},
    "llm_synthesis_vs_voting": "COMPREHENSIVE comparison (200-300 words). Analyze: (1) How the LLM synthesis outcome compares to majority voting, (2) Whether debate added value beyond simple voting, (3) What nuances the synthesis captured that voting missed, (4) Any discrepancies between the two approaches and why they exist, (5) Implications for decision-making"
  }}
}}

IMPORTANT: Each text field must be comprehensive and detailed. Do not provide brief summaries. Provide complete, substantive analysis with specific details, reasoning, and evidence."""

        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(
            messages, thinking=False, temperature=0.6, max_tokens=20000, timeout=900
        )

    def compress_wildcards(self, wildcard_factors: list) -> list:
        """Generate search queries from wildcard factors."""
        return wildcard_factors[:3]  # Limit to 3

    def check_token_budget(self, round_history: list) -> bool:
        """Check if approaching token limit."""
        history_text = json.dumps(round_history)
        self.token_count = self.estimate_tokens(history_text)
        return self.token_count > COMPRESSION_THRESHOLD

    def second_order_compression(self, round_history: list) -> list:
        """Collapse oldest half of rounds into single summary."""
        if len(round_history) <= 2:
            return round_history

        midpoint = len(round_history) // 2
        old_rounds = round_history[:midpoint]
        new_rounds = round_history[midpoint:]

        # Compress old rounds into single summary
        old_text = json.dumps(old_rounds)
        prompt = f"""Collapse these old rounds into a single summary:

{old_text}

Return JSON with this structure:
{{
  "round": "early_history",
  "dominant_positions": ["string"],
  "notable_shifts": ["string"],
  "emerging_coalitions": ["string"],
  "key_exchanges": ["string"],
  "note": "Compressed summary of early rounds"
}}"""

        compressed = self.call_llm(
            [{"role": "user", "content": prompt}], thinking=False, temperature=0.7
        )

        return [compressed] + new_rounds

    def calculate_expertise_score(self, persona: dict, situation: dict) -> dict:
        """
        Calculate expertise score based on experience and domain match.

        Args:
            persona: Persona dict with role_title, years_experience, etc.
            situation: Situation dict from Stage 1 with domain, disciplines, etc.

        Returns:
            {
                "expertise_score": 0-100,
                "experience_level": 0-100,
                "domain_match": 0-100
            }
        """
        # Component 1: Experience Level (50% weight)
        years_exp = persona.get("years_experience", "0")
        try:
            years = int(years_exp)
        except:
            years = 0
        experience_score = min(100, years * 5)

        # Component 2: Domain Match (50% weight)
        domain = situation.get("domain", "social")
        role_type = persona.get("role_type", "Unknown")
        domain_match = self._calculate_domain_match(domain, role_type)

        # Calculate weighted expertise score
        expertise = 0.5 * experience_score + 0.5 * domain_match

        return {
            "expertise_score": round(expertise, 1),
            "experience_level": round(experience_score, 1),
            "domain_match": round(domain_match, 1),
        }

    def _calculate_domain_match(self, domain: str, role_type: str) -> float:
        """Calculate how well role matches the situation domain."""
        domain_role_mapping = {
            "geopolitical": [
                "policy analyst",
                "diplomat",
                "ngo director",
                "industry lobbyist",
                "academic researcher",
                "community advocate",
                "foreign policy",
                "government official",
                "political strategist",
            ],
            "financial": [
                "portfolio manager",
                "risk analyst",
                "regulatory compliance",
                "investment strategist",
                "economist",
                "consumer advocate",
                "financial analyst",
                "trader",
                "banker",
            ],
            "technical": [
                "senior engineer",
                "research scientist",
                "product manager",
                "security expert",
                "open source contributor",
                "enterprise architect",
                "software engineer",
                "data scientist",
                "devops",
            ],
            "interpersonal": [
                "family therapist",
                "mediator",
                "psychologist",
                "cultural advisor",
                "conflict resolution specialist",
                "counselor",
                "social worker",
            ],
            "social": [
                "sociologist",
                "community leader",
                "policy analyst",
                "researcher",
                "advocate",
                "activist",
                "social worker",
            ],
        }

        # Check if role_type is in relevant roles for domain
        relevant_roles = domain_role_mapping.get(domain, [])
        role_lower = role_type.lower()

        # Check for direct match
        if any(role in role_lower for role in relevant_roles):
            return 95.0

        # Check for partial match (common words overlap)
        domain_keywords = {
            "geopolitical": [
                "policy",
                "government",
                "political",
                "international",
                "diplomacy",
            ],
            "financial": ["finance", "economic", "investment", "market", "money"],
            "technical": [
                "engineering",
                "technology",
                "software",
                "science",
                "technical",
            ],
            "interpersonal": [
                "therapy",
                "psychology",
                "mediation",
                "counseling",
                "relationship",
            ],
            "social": ["social", "community", "sociology", "advocacy"],
        }

        keywords = domain_keywords.get(domain, [])
        if any(keyword in role_lower for keyword in keywords):
            return 80.0

        # Unknown or mismatched
        return 50.0

    def calculate_majority_voting(
        self,
        personas: list,
        round_history: list,
        use_weighting: bool = False,
        situation: Optional[dict] = None,
    ) -> dict:
        """
        Calculate majority voting with optional expertise weighting.

        Args:
            personas: List of persona dicts
            round_history: List of compressed round data
            use_weighting: If True, weight votes by expertise × confidence
            situation: Situation dict for domain context (required for weighting)

        Returns:
            {
                "majority_outcome": "support|oppose|compromise",
                "vote_distribution": {"support": N, "oppose": N, "compromise": N},
                "weighted_majority_outcome": "string or None",
                "weighted_vote_distribution": {"support": N.N, ...} or None,
                "total_votes": N,
                "majority_percentage": float
            }
        """
        stance_counts = {"support": 0, "oppose": 0, "compromise": 0}
        weighted_stance_counts = {"support": 0.0, "oppose": 0.0, "compromise": 0.0}

        for persona in personas:
            # Extract stance from initial position
            initial_pos = persona.get("initial_position", "")
            stance = self._extract_stance_from_position(initial_pos)

            # Simple vote count
            if stance in stance_counts:
                stance_counts[stance] += 1

            # Weighted vote if enabled
            if use_weighting and stance in weighted_stance_counts:
                # Get confidence (from persona if available, default 50)
                confidence = persona.get("confidence_score", 50)

                # Get expertise score
                if situation:
                    expertise_data = self.calculate_expertise_score(persona, situation)
                    expertise = expertise_data.get("expertise_score", 50)
                else:
                    expertise = 50.0

                # Calculate weight (normalized to 0-1)
                weight = (confidence * expertise) / 10000.0

                weighted_stance_counts[stance] += weight

        # Determine outcomes
        majority_stance = max(stance_counts, key=stance_counts.get)
        weighted_majority = (
            max(weighted_stance_counts, key=weighted_stance_counts.get)
            if use_weighting
            else None
        )

        # Calculate percentages
        total_simple = sum(stance_counts.values())
        majority_percentage = (
            round(stance_counts[majority_stance] / total_simple * 100, 1)
            if total_simple > 0
            else 0
        )

        # Calculate weighted percentages
        total_weighted = sum(weighted_stance_counts.values())
        weighted_percentage = (
            round(weighted_stance_counts[weighted_majority] / total_weighted * 100, 1)
            if (total_weighted > 0 and weighted_majority)
            else 0
        )

        result = {
            "majority_outcome": majority_stance,
            "vote_distribution": stance_counts,
            "total_votes": total_simple,
            "majority_percentage": majority_percentage,
        }

        if use_weighting:
            result["weighted_majority_outcome"] = weighted_majority
            result["weighted_vote_distribution"] = {
                k: round(v, 2) for k, v in weighted_stance_counts.items()
            }
            result["weighted_majority_percentage"] = weighted_percentage

        return result

    def _extract_stance_from_position(self, position: str) -> str:
        """Extract stance (support/oppose/compromise) from position text."""
        if not position:
            return "neutral"

        pos_lower = position.lower()

        if any(
            word in pos_lower
            for word in [
                "support",
                "favor",
                "advocate",
                "pro",
                "should",
                "must",
                "agree",
            ]
        ):
            return "support"
        elif any(
            word in pos_lower
            for word in [
                "oppose",
                "against",
                "reject",
                "concern",
                "risk",
                "danger",
                "opposed",
            ]
        ):
            return "oppose"
        elif any(
            word in pos_lower
            for word in ["compromise", "middle", "balance", "moderate", "both sides"]
        ):
            return "compromise"

        return "neutral"

    def extract_fact_checking_queries(
        self, round_responses: list, situation: dict
    ) -> list:
        """
        Extract factual claims and questions from round responses that need verification.

        Args:
            round_responses: List of persona responses from current round
            situation: Situation dict from Stage 1

        Returns:
            List of search queries for fact-checking
        """
        queries = []

        # Extract key factual claims from positions
        for response in round_responses:
            position = response.get("position", "")

            # Pattern 1: Specific claims with numbers/dates
            number_claims = self._extract_number_claims(position)
            queries.extend(number_claims)

            # Pattern 2: Causal assertions
            causal_claims = self._extract_causal_claims(position)
            queries.extend(causal_claims)

            # Pattern 3: Counter-arguments needing verification
            counter_claims = self._extract_counter_claims(position)
            queries.extend(counter_claims)

        # Add wildcard factors from situation if available
        wildcard_factors = situation.get("wildcard_factors", [])
        queries.extend(wildcard_factors[:2])

        # Deduplicate and limit to top 5 queries
        queries = list(dict.fromkeys(queries))[:5]  # Preserve order while deduplicating

        return queries

    def _extract_number_claims(self, text: str) -> list:
        """Extract queries based on numerical claims in text."""
        import re

        queries = []

        # Find percentages and numbers
        patterns = [
            (r"(\d+)%", "percentage"),
            (r"(\d{3,})", "large number"),
            (r"(\d+\.\d+)", "decimal"),
            (r"(\d{4})", "year"),
        ]

        for pattern, ptype in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # Create query based on context
                query = f"verify {text[:100]}..."
                queries.append(query)

        return queries[:2]  # Limit to 2 queries

    def _extract_causal_claims(self, text: str) -> list:
        """Extract queries based on causal assertions."""
        queries = []

        causal_patterns = [
            r"causes? [^\.]+",
            r"leads to [^\.]+",
            r"results in [^\.]+",
            r"will [a-z]+ [^\.]+",
            r"increases? [^\.]+",
            r"decreases? [^\.]+",
        ]

        for pattern in causal_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                query = f"evidence for {matches[0][:80]}"
                queries.append(query)

        return queries[:2]

    def _extract_counter_claims(self, text: str) -> list:
        """Extract queries based on counter-arguments or opposing views."""
        queries = []

        counter_patterns = [
            r"opponents? argue [^\.]+",
            r"critics? claim [^\.]+",
            r"however [^\.]+",
            r"on the other hand [^\.]+",
        ]

        for pattern in counter_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                query = f"validity of {matches[0][:80]}"
                queries.append(query)

        return queries[:1]

    def generate_scenario_suggestions(self, context: dict) -> list:
        """Generate scenario suggestions from context file."""
        prompt = f"""Based on this context, generate 3-5 scenario suggestions:

Interests: {context.get("interests", [])}
Tracked Situations: {context.get("tracked_situations", [])}
Key Actors: {context.get("key_actors", [])}
Analytical Priors: {context.get("analytical_priors", [])}

Return a JSON array of scenario descriptions (strings only)."""

        messages = [{"role": "user", "content": prompt}]
        return self.call_llm(messages, thinking=False, temperature=0.8)
