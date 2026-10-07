import logging
from typing import Optional
import config

logger = logging.getLogger("DramaticNarrator.AI")

SYSTEM_PROMPT = """You are 'The Dramatic Narrator' and 'Server Historian' of a lively Discord server with a group of friends.
Your job is to entertain the server with hilarious, dramatic commentary, recaps, and lighthearted roasts.

Core Persona Traits:
1. Easy to Understand & Modern: Do NOT use difficult, obscure, or overly archaic vocabulary (avoid verbose purple prose or hard-to-read old English). Keep the language simple, fast-paced, modern, and accessible.
2. Peak Comedy & Relatable Drama: The humor comes from treating ordinary, everyday server nonsense (arguments over food, gaming fails, random typos, someone ghosting, hot takes) like it's earth-shattering reality TV drama or an intense movie scene.
3. Punchy & Readable: Keep paragraphs short, punchy, and well-formatted with Discord markdown (bullet points, bold text).
4. Good Vibes Only: Never be actually hateful, toxic, or cruel. Roasts must be affectionate, witty, and fun for everyone in the group to laugh at together.
"""

STYLE_PROMPTS = {
    "reality_tv": (
        "Genre: Messy Reality TV Show (Love Island / Real Housewives).\n"
        "Style: Gossipy, chaotic confessionals, fake gasp moments, dramatic betrayal music, and petty drama. Super fast-paced, modern, and hilarious."
    ),
    "courtroom": (
        "Genre: Chaotic Courtroom Trial / Judge Judy.\n"
        "Style: High-stakes courtroom hearing where petty chat arguments are treated like federal crimes. Point out who is 'on trial', the laughable 'evidence', and deliver an unhinged final verdict."
    ),
    "breaking_news": (
        "Genre: Sensational Breaking News / Hyped Sports Caster.\n"
        "Style: 'WE INTERRUPT YOUR PROGRAMMING!' Urgent anchors, dramatic live correspondents on the scene, breaking chyrons, and breathless play-by-play commentary of silly server moments."
    ),
    "medieval": (
        "Genre: Medieval Fantasy Drama (Game of Thrones parody).\n"
        "Style: Playful kingdoms at war, royal treason, and tavern arguments—but using clear, funny, modern English that anyone can instantly get."
    ),
    "nature_doc": (
        "Genre: Wildlife Nature Documentary.\n"
        "Style: David Attenborough whispering in awe, scientifically analyzing the bizarre mating calls, territorial squabbles, and feeding habits of wild Discord creatures."
    ),
}

class AIService:
    def __init__(self):
        self.provider = config.AI_PROVIDER
        self._gemini_client = None
        self._openai_client = None
        self._init_client()

    def _init_client(self):
        if self.provider == "gemini":
            try:
                # Prefer google-genai modern SDK
                from google import genai
                self._gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
                logger.info(f"Initialized Google GenAI Client with model {config.GEMINI_MODEL}")
            except Exception as e:
                logger.warning(f"Could not initialize google.genai: {e}. Trying google.generativeai fallback...")
                try:
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=config.GEMINI_API_KEY)
                    self._gemini_client = legacy_genai.GenerativeModel(
                        model_name=config.GEMINI_MODEL,
                        system_instruction=SYSTEM_PROMPT
                    )
                    logger.info("Initialized legacy google.generativeai fallback.")
                except Exception as e2:
                    logger.error(f"Failed to initialize Gemini: {e2}")

        elif self.provider == "openai":
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
                logger.info(f"Initialized AsyncOpenAI Client with model {config.OPENAI_MODEL}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")

    async def generate_response(self, user_prompt: str, system_override: Optional[str] = None) -> str:
        prompt_system = system_override or SYSTEM_PROMPT

        if self.provider == "gemini" and self._gemini_client:
            # Check if modern google-genai
            if hasattr(self._gemini_client, "aio") and hasattr(self._gemini_client.aio, "models"):
                from google.genai import types
                response = await self._gemini_client.aio.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=prompt_system,
                        temperature=0.85,
                    )
                )
                return response.text.strip()
            # Legacy google.generativeai fallback
            elif hasattr(self._gemini_client, "generate_content_async"):
                response = await self._gemini_client.generate_content_async(
                    contents=user_prompt,
                    generation_config={"temperature": 0.85}
                )
                return response.text.strip()

        elif self.provider == "openai" and self._openai_client:
            response = await self._openai_client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.85,
            )
            return response.choices[0].message.content.strip()

        raise RuntimeError(
            f"AI provider '{self.provider}' is not properly initialized. Check your API keys and configuration."
        )

    async def generate_recap(self, messages_text: str, style_key: str = "medieval") -> str:
        style_instruction = STYLE_PROMPTS.get(style_key, STYLE_PROMPTS["medieval"])
        prompt = (
            f"{style_instruction}\n\n"
            f"TASK:\n"
            f"Read the recent chat transcript below and write a hilarious, dramatic, and easy-to-read recap.\n\n"
            f"RULES FOR RECAP:\n"
            f"- Easy to Read: Use clear, simple, conversational language with lots of humor. No fancy, obscure, or old-fashioned words.\n"
            f"- Dramatic Fun: Dramatize what the group actually talked about (e.g. food debates, gaming moments, memes, random arguments).\n"
            f"- Structure: Use bold titles and 2-4 short bullet points highlighting key moments/clashes, ending with a funny one-line dramatic prophecy.\n\n"
            f"RECENT CHAT:\n"
            f"---\n"
            f"{messages_text}\n"
            f"---\n\n"
            f"DRAMATIC RECAP:"
        )
        return await self.generate_response(prompt)

    async def generate_roast(self, username: str, user_messages: str, spice_level: str = "medium") -> str:
        spice_note = {
            "mild": "Playful poke and friendly tease.",
            "medium": "Savagely funny and witty, but affectionate.",
            "spicy": "Peak comedy burn! Ruthless comedic roast of their quirks, but strictly friendly Discord humor."
        }.get(spice_level, "Savagely funny and witty.")

        prompt = (
            f"TARGET MEMBER: {username}\n"
            f"SPICE LEVEL: {spice_level.upper()} ({spice_note})\n\n"
            f"CHAT ACTIVITY OF {username}:\n"
            f"---\n"
            f"{user_messages}\n"
            f"---\n\n"
            f"TASK:\n"
            f"Deliver a SHORT, SUPER PUNCHY, and HILARIOUS roast of {username} based directly on their messages above.\n\n"
            f"CRITICAL RULES:\n"
            f"1. KEEP IT SHORT: Exactly 2 to 4 punchy sentences maximum (around 40-75 words total). Do NOT write a long paragraph or essay!\n"
            f"2. SIMPLE & RELATABLE LANGUAGE: Use clean, modern, easy-to-understand conversational English. No ancient words, no Shakespearean talk, no complicated vocabulary.\n"
            f"3. CALL OUT REAL HABITS: Point out their actual habits from the messages (e.g., terrible excuses, typing in all caps, sending random takes, weird emoji habits, constantly disappearing).\n"
            f"4. PEAK COMEDY: Make it sound like a quick, witty roast comic delivering a hilarious burn that will make the whole server laugh.\n\n"
            f"HILARIOUS ROAST:"
        )
        return await self.generate_response(prompt)

    async def generate_chronicle(self, title: str, description: str, recorder_name: str) -> str:
        prompt = (
            f"A server member ({recorder_name}) submitted this event to the archives: '{title}'\n"
            f"Event details: \"{description}\"\n\n"
            f"TASK:\n"
            f"Rewrite this event as an epic, funny chronicle in clear and easy-to-understand modern English. "
            f"Keep it to 2 short, entertaining paragraphs declaring this event an unforgettable legend in server history."
        )
        return await self.generate_response(prompt)
