from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.openai_api_key)

def generate_estimation(system: str, user: str) -> str:
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": system
            },
            {
                "role": "user",
                "content": user
            },
        ],
    )

    return response.choices[0].message.content