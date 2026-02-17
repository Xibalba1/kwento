STORY_SYNOPSIS_PROMPT_PREFACE = """
**TITLE**: **CHILDREN'S BOOK STORY SYNOPSIS**

**INSTRUCTIONS**: Generate a detailed synopsis of a children’s book storyline. Use the following structure and guidelines to ensure the narrative is engaging, age-appropriate, and easy to follow.

**Age Range**: {age_range}

**Key Elements**:
    - **Setting**:
        - Choose a unique, friendly environment (e.g., a small village at the edge of an enchanted forest, a cozy seaside town dotted with whimsical cottages, or a hillside orchard where tiny creatures build their homes).
        - Include sensory details (colorful flora, gentle breezes, distant laughter, or twinkling lanterns) that children can visualize.
    - **Main Character**:
        - Introduce a likable, relatable protagonist (e.g., a curious child, a gentle animal, or a young inventor) with a simple, heartfelt goal.
        - Consider a desire that feels meaningful yet attainable (e.g., finding a treasured family heirloom, understanding a strange new sound in the forest, or helping a friend in need).
    - **Supporting Characters**:
        - In most but not all cases, there should be a cast of supporting characters
        - These may be friends, family, strangers, or villains
    - **Conflict or Challenge**:
        - Present an obstacle (e.g., a puzzle that requires cooperation, a misunderstanding that needs clearing up, a nefarious villain, etc.).
        - Emphasize positive attributes (e.g., bravery, kindness, determination, etc.) as tools for resolving the conflict.
    - **Plot Development**:
        - Outline key events in a logical sequence.
        - Include twists or surprises that encourage curiosity without introducing too much fear or despair.
        - Let the characters learn from one another, making small discoveries that guide them toward a solution.
    - **Resolution**:
        - Conclude with a satisfying, uplifting ending that imparts a simple, meaningful lesson (e.g., the importance of kindness, the value of perseverance, or the joy of understanding others).
        - Reinforce positive themes and leave room for children to imagine the characters’ lives continuing afterward.
**Tone and Style**:
    - Words and sentences appropriate in length and complexity for *Age Range*
    - Accessible, lively, and engaging language
    - Encourage imagination, humor, and fun
**RESPONSE**:
    - **Structure**:
        - Your response *MUST* be the form of a *JSON* blob.
    - **Structure Template**:
```
{synopsis_structure}
```
"""
STORY_SYNOPSIS_STRUCTURE = {
    "book_title": "string (maximum 10 tokens / 30 characters, the title of the book)",
    "synopsis": {
        "setting": "string (maximum 100 tokens / 500 characters, describes the setting of the story)",
        "main_character": {
            "name": "string (maximum 10 tokens / 30 characters, name of the main character)",
            "age": "integer (age of the main character)",
            "traits": "string (maximum 50 tokens / 250 characters, description of key personality traits and abilities)",
            "objective": "string (maximum 30 tokens / 150 characters, the main character's goal or aspiration)",
        },
        "supporting_characters": [
            {
                "name": "string (maximum 10 tokens / 30 characters, name of the supporting character)",
                "role": "string (maximum 30 tokens / 150 characters, role in the story)",
                "personality": "string (maximum 30 tokens / 150 characters, description of personality or unique traits)",
                "appearance": "string (maximum 30 tokens / 150 characters, description of personality or unique traits)",
            }
        ],
        "conflict_or_challenge": "string (maximum 100 tokens / 500 characters, central problem or challenge of the story)",
        "plot_development": {
            "introduction": "string (maximum 50 tokens / 250 characters, how the story begins and sets up the problem)",
            "events": [
                "string (maximum 100 tokens / 500 characters, key events or milestones in the story)"
            ],
            "resolution": "string (maximum 50 tokens / 250 characters, how the story's conflict is resolved)",
        },
        "lesson": "string (maximum 30 tokens / 150 characters, main moral or lesson of the story)",
        "tone_and_style": "string (maximum 50 tokens / 250 characters, tone and narrative style of the story)",
    },
}


if __name__ == "__main__":
    story_synopsis_prompt = STORY_SYNOPSIS_PROMPT_PREFACE.format(
        age_range="18 to 30 months old", synopsis_structure=STORY_SYNOPSIS_STRUCTURE
    )
    print(story_synopsis_prompt)
