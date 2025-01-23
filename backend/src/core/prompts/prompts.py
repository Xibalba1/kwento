PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS = """Write a children's book. IMPORTANT!! ENSURE YOUR RESPONSE IS **LESS** THAN 1301 WORDS / 2201 TOTAL_TOKENS.:
 - **Theme**: {theme}
 - **Plot**:
    - Interesting, adventurous, and fun!
    - Relevant in some way to lives or imaginations of the intended audience
- **Book Title**:
  - Should capture the spirit of adventure, theme, and emotion in the story, without being too direct or generic.
  - Aim for a unique, memorable, and evocative title that appeals to children’s imaginations.
  - Avoid overly descriptive titles that summarize the story; instead, think of titles that spark curiosity and wonder about the character’s journey or adventure.
 - **Reading level**: early toddlers.
 - **Characters**:
    - There should be between 1 and 5 characters in the book
    - Characters should have distinct personalities and behaviors
    - Character appearances should be distinct in size, coloring, clothing, facial and body features, and these attributes should distinguish them from one another
    - Any character present in any `page` > `characters_in_this_page` *MUST* also be present *ONCE AND ONLY ONCE* in `characters`
    - Names used in `page` > `characters_in_this_page` must *EXACTLY* match names present in `characters`
 - **Setting**:
    - There should be at least one if not multiple setting changes.
    - Setting changes can be moderate (Ex: moving from one room of a building to another) or dramatic (Ex: traveling from galaxy to another!)
    - Be sure to describe the setting in `illustration` values for each page so that the generated illustrations can maintain visual consistency when there is not a setting change. (Ex: if an elephant and a monkey are climbing a hill, mention the hill in each page when that action is ongoing.)
 - **`book_length_n_pages`**
    - Length may vary as needed, consistent with the reading level of the intended audience
    - The parameter of 10 in the example output format below is an example only
    - number of entries in `pages` should *EXACTLY* match `book_length_n_pages`
    - ensure the number of pages *WILL NOT* result in a response greater than 1301 WORDS / 2201 TOTAL_TOKENS
 - **`illustration_values`**:
    - *DO NOT* include any dialogue or text to be depicted in the image. All dialogue should be in the `text_content_of_this_page` value for a given page.
    - Will be used to generate images, so, to keep them coherent, make sure to mention the setting of the image, even if the setting is the same as in the previous page. The setting should be described in detail in `illustration` values.
    - should include the description of characters' action, poses, movements, and/or facial expression where warranted. We don't want illustrations that are boring or overly static.
 - **`characters`>`appearance`**:
    - should be very descriptive
    - These descriptions will be used to generate multiple images, so we need sufficient detail to generate consistent depictions of the characters. 
 - **Ensure output is valid JSON (i.e. no syntax errors, opening/closing braces match, escape double quotes in strings, etc.)**
 - **Your response length**: *DO NOT EXCEED 1301 WORDS / 2201 TOTAL_TOKENS* Consider this length limit in determing all parameter values!!
 
OUTPUT FORMAT:
"""

TEMPLATE_CHILDRENS_BOOK = """```{"book_title":"The title of the book","book_length_n_pages":10,"characters":[{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."},{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."}],"plot_synopsis":"Plot synopsis.","pages":[{"page_number":1,"content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}},{"page_number":2,"content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}}]}```
"""

THEMES = [
    "Embracing individuality and self-expression",
    "The value of kindness in everyday life",
    "Overcoming fears through bravery",
    "Finding joy in helping others",
    "The beauty of imagination and creativity",
    "Exploring the wonders of nature",
    "Building confidence by facing challenges",
    "Respecting different cultures and perspectives",
    "The power of teamwork and collaboration",
    "Discovering the magic of friendship",
    "Learning from mistakes and failure",
    "Developing patience in a fast-paced world",
    "The importance of honesty and trust",
    "Exploring the power of dreams and goals",
    "The joy of learning and asking questions",
    "Protecting the environment and loving animals",
    "Understanding the value of family and togetherness",
    "The adventure of trying new things",
    "Being compassionate and caring for others",
    "Celebrating diversity and differences",
    "Standing up for what’s right, even when it’s hard",
    "Building a growth mindset and loving learning",
    "Developing a love for music and art",
    "The importance of responsibility and doing your best",
    "Accepting change and adapting to new situations",
    "The joy of giving and sharing with others",
    "Persevering when things get tough",
    "Learning how to be a good listener",
    "Building healthy habits and self-care",
    "Appreciating the little things in life",
    "Cultivating curiosity and exploring the unknown",
    "Understanding emotions and expressing them",
    "The importance of sharing and generosity",
    "Facing loneliness and discovering self-worth",
    "Building empathy and understanding others' feelings",
    "Balancing fun with hard work",
    "Appreciating the power of forgiveness",
    "Managing conflicts with kindness and wisdom",
    "Finding strength in family bonds",
    "Discovering that home is more than just a place",
]

ILLUSTRATION_STYLE_ATTRIBUTES = [
    {
        "Color Palette": "Bright, Textured",
        "Line Quality": "Loose",
        "Texture": "Collaged",
        "Character Style": "Simple, Playful",
        "Perspective": "Flat",
        "Movement": "Fluid",
        "Composition": "Balanced",
        "Use of Space": "Full-page",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Joyful",
        "Medium": "Collage, Paper",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Muted, Earthy",
        "Line Quality": "Detailed",
        "Texture": "Soft",
        "Character Style": "Realistic, Whimsical",
        "Perspective": "3D",
        "Movement": "Subtle",
        "Composition": "Crowded",
        "Use of Space": "Framed, In-depth",
        "Lighting": "Dramatic",
        "Mood/Atmosphere": "Dark, Whimsical",
        "Medium": "Pencil, Ink, Watercolor",
        "Detail Level": "Detailed",
    },
    {
        "Color Palette": "Bright, Bold",
        "Line Quality": "Exaggerated",
        "Texture": "Smooth",
        "Character Style": "Cartoonish",
        "Perspective": "Dynamic",
        "Movement": "Energetic",
        "Composition": "Symmetrical",
        "Use of Space": "Edge-to-edge",
        "Lighting": "High Contrast",
        "Mood/Atmosphere": "Playful",
        "Medium": "Ink, Watercolor",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Soft, Natural",
        "Line Quality": "Fine, Detailed",
        "Texture": "Smooth",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Symmetrical",
        "Use of Space": "Bordered",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Gentle, Peaceful",
        "Medium": "Watercolor, Ink",
        "Detail Level": "Detailed",
    },
    {
        "Color Palette": "Vibrant, Loose",
        "Line Quality": "Sketchy",
        "Texture": "Minimal",
        "Character Style": "Whimsical",
        "Perspective": "Flat",
        "Movement": "Lively",
        "Composition": "Asymmetrical",
        "Use of Space": "Floating Elements",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Humorous",
        "Medium": "Watercolor, Ink",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Warm, Bright",
        "Line Quality": "Bold, Clean",
        "Texture": "Flat",
        "Character Style": "Simple",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Centered",
        "Use of Space": "Full-page",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Cheerful",
        "Medium": "Watercolor, Ink",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Warm, Contrasting",
        "Line Quality": "Bold, Simple",
        "Texture": "Collaged",
        "Character Style": "Realistic",
        "Perspective": "Flat",
        "Movement": "Fluid",
        "Composition": "Minimal",
        "Use of Space": "Full-page, Bleed-off",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Urban, Realistic",
        "Medium": "Mixed Media",
        "Detail Level": "Moderate",
    },
    {
        "Color Palette": "Earthy, Muted",
        "Line Quality": "Textured",
        "Texture": "Rough",
        "Character Style": "Quirky",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Crowded",
        "Use of Space": "Dense, Full-page",
        "Lighting": "Soft, Shadowed",
        "Mood/Atmosphere": "Surreal",
        "Medium": "Digital, Acrylic",
        "Detail Level": "Detailed",
    },
    {
        "Color Palette": "Muted, Monochrome",
        "Line Quality": "Precise",
        "Texture": "Smooth",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Centered",
        "Use of Space": "Edge-to-edge",
        "Lighting": "Dramatic",
        "Mood/Atmosphere": "Mysterious",
        "Medium": "Pencil, Charcoal",
        "Detail Level": "Highly Detailed",
    },
    {
        "Color Palette": "Earthy, Natural",
        "Line Quality": "Minimalist",
        "Texture": "Rough",
        "Character Style": "Abstract",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Balanced",
        "Use of Space": "Full-page, Inlay",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Simple",
        "Medium": "Collage, Paper",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Soft, Vibrant",
        "Line Quality": "Precise",
        "Texture": "Smooth",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Fluid",
        "Composition": "Dynamic",
        "Use of Space": "Full-page",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Dreamy, Surreal",
        "Medium": "Watercolor, Pencil",
        "Detail Level": "Highly Detailed",
    },
    {
        "Color Palette": "Pastel, Muted",
        "Line Quality": "Clean",
        "Texture": "Flat",
        "Character Style": "Cartoonish",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Centered",
        "Use of Space": "White space, Simple",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Humorous",
        "Medium": "Digital, Ink",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Warm, Bright",
        "Line Quality": "Detailed",
        "Texture": "Textured",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Crowded",
        "Use of Space": "Decorative Borders",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Cheerful, Rich",
        "Medium": "Watercolor, Ink",
        "Detail Level": "Highly Detailed",
    },
    {
        "Color Palette": "Muted, Warm",
        "Line Quality": "Childlike",
        "Texture": "Flat",
        "Character Style": "Simple, Whimsical",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Minimal",
        "Use of Space": "White space",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Whimsical",
        "Medium": "Ink, Watercolor",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Pastel, Soft",
        "Line Quality": "Clean",
        "Texture": "Flat",
        "Character Style": "Cartoonish",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Balanced",
        "Use of Space": "White space",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Gentle",
        "Medium": "Watercolor, Ink",
        "Detail Level": "Moderate",
    },
    {
        "Color Palette": "Monochrome",
        "Line Quality": "Detailed",
        "Texture": "Smooth",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Asymmetrical",
        "Use of Space": "Full-page",
        "Lighting": "Dramatic",
        "Mood/Atmosphere": "Suspenseful",
        "Medium": "Pencil, Charcoal",
        "Detail Level": "Highly Detailed",
    },
    {
        "Color Palette": "Warm, Pastel",
        "Line Quality": "Loose",
        "Texture": "Smooth",
        "Character Style": "Simple",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Minimal",
        "Use of Space": "White space",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Gentle, Warm",
        "Medium": "Watercolor, Ink",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Muted, Earthy",
        "Line Quality": "Clean, Simple",
        "Texture": "Flat",
        "Character Style": "Minimalistic",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Balanced",
        "Use of Space": "White space",
        "Lighting": "Soft, Shadowed",
        "Mood/Atmosphere": "Subtle",
        "Medium": "Digital, Ink",
        "Detail Level": "Minimalistic",
    },
    {
        "Color Palette": "Black & White",
        "Line Quality": "Loose, Sketchy",
        "Texture": "None",
        "Character Style": "Exaggerated",
        "Perspective": "Flat",
        "Movement": "Static",
        "Composition": "Centered",
        "Use of Space": "White space",
        "Lighting": "High Contrast",
        "Mood/Atmosphere": "Humorous",
        "Medium": "Ink",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Bright, Busy",
        "Line Quality": "Bold, Simple",
        "Texture": "Smooth",
        "Character Style": "Cartoonish",
        "Perspective": "Flat",
        "Movement": "Lively",
        "Composition": "Crowded",
        "Use of Space": "Full-page",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Playful",
        "Medium": "Ink, Watercolor",
        "Detail Level": "Moderate",
    },
    {
        "Color Palette": "Warm, Earthy",
        "Line Quality": "Fine, Detailed",
        "Texture": "Textured",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Balanced",
        "Use of Space": "Full-page",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Warm, Gentle",
        "Medium": "Watercolor",
        "Detail Level": "Highly Detailed",
    },
    {
        "Color Palette": "Bold, Bright",
        "Line Quality": "Bold",
        "Texture": "Textured",
        "Character Style": "Simple",
        "Perspective": "Flat",
        "Movement": "Fluid",
        "Composition": "Minimal",
        "Use of Space": "Negative Space",
        "Lighting": "Natural",
        "Mood/Atmosphere": "Cheerful",
        "Medium": "Mixed Media",
        "Detail Level": "Simple",
    },
    {
        "Color Palette": "Soft, Natural",
        "Line Quality": "Fine, Delicate",
        "Texture": "Smooth",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Balanced",
        "Use of Space": "Framed, Centered",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Nostalgic",
        "Medium": "Watercolor, Ink",
        "Detail Level": "Moderate",
    },
    {
        "Color Palette": "Rich, Warm",
        "Line Quality": "Fine, Precise",
        "Texture": "Smooth",
        "Character Style": "Realistic",
        "Perspective": "3D",
        "Movement": "Static",
        "Composition": "Symmetrical",
        "Use of Space": "Full-page",
        "Lighting": "Dramatic",
        "Mood/Atmosphere": "Classical",
        "Medium": "Oil, Acrylic",
        "Detail Level": "Highly Detailed",
    },
    {
        "Color Palette": "Muted, Natural",
        "Line Quality": "Loose",
        "Texture": "Textured",
        "Character Style": "Whimsical",
        "Perspective": "Flat",
        "Movement": "Fluid",
        "Composition": "Balanced",
        "Use of Space": "White space",
        "Lighting": "Soft",
        "Mood/Atmosphere": "Playful",
        "Medium": "Watercolor, Pencil",
        "Detail Level": "Moderate",
    },
]
PROMPT_PAGE_ILLUSTRATION_PREFACE = """Create an illustration for children's book according to the following specification (follow the specification *EXACTLY*):"""
PROMPT_PAGE_ILLUSTRATION_BODY = {
    "SYSTEM_NOTES": {
        "1": "*NEVER* depict text in the generated image.",
        "2": "You are *NOT* creating an image of the act of illustration, nor an illustration in a book. You are creating an illustration to be placed in a book.",
        "3": "Characters *MUST* be in action. *NOT* staring at each other or the reader.",
    },
    "illustration_description": None,  # text description of the page's illustration
    "illustration_style": {
        "Dimensionality/Depth": None,
        "Color Palette": None,
        "Line Quality": None,
        "Texture": None,
        "Character Style": None,
        "Perspective": None,
        "Movement": None,
        "Composition": None,
        "Use of Space": None,
        "Lighting": None,
        "Mood/Atmosphere": None,
        "Medium": None,
        "Detail Level": None,
    },
    "characters_in_illustration": [
        # {
        #     "name": None,
        #     "appearance": None,
        # }
    ],
    "text_content": None,  # text that appears on the page (context for illustration)
}
AT_SYNOPSIS_PROMPT_PREFACE = """
**TITLE**: **CHILDREN'S BOOK STORY SYNOPSIS**

**INSTRUCTIONS**: Generate a detailed synopsis of a children’s book storyline. Use the following structure and guidelines to ensure the narrative is engaging, age-appropriate, and easy to follow.

**Age Range**: {age_range}

**Key Elements**:

    - **Setting**:
        - Choose a unique, friendly environment (e.g., a small village at the edge of an enchanted forest, a cozy seaside town dotted with whimsical cottages, or a hillside orchard where tiny creatures build their homes).
        - Include sensory details (colorful flora, gentle breezes, distant laughter, or twinkling lanterns) that children can visualize.

    - **Main Character:
        - Introduce a likable, relatable protagonist (e.g., a curious child, a gentle animal, or a young inventor) with a simple, heartfelt goal.
        - Consider a desire that feels meaningful yet attainable (e.g., finding a treasured family heirloom, understanding a strange new sound in the forest, or helping a friend in need).

    - **Supporting Characters:
        - In most but not all cases, there should be a cast of supporting characters
        - These may be friends, family, strangers, or villains

    - **Conflict or Challenge:
        - Present a friendly, non-threatening obstacle (e.g., a puzzle that requires cooperation, a misunderstanding that needs clearing up, or a natural element like a missing bridge).
        - Emphasize teamwork, empathy, and creativity as tools for resolving the conflict.

    - **Plot Development:
        - Outline key events in a logical, easy-to-follow sequence.
        - Include gentle twists or surprises that encourage curiosity without introducing fear or despair.
        - Let the characters learn from one another, making small discoveries that guide them toward a solution.

    - **Resolution:
        - Conclude with a satisfying, uplifting ending that imparts a simple, meaningful lesson (e.g., the importance of kindness, the value of perseverance, or the joy of understanding others).
        - Reinforce positive themes and leave room for children to imagine the characters’ lives continuing happily afterward.

**Tone and Style**:
    - Maintain a warm, optimistic atmosphere.
    - Use language that is accessible, lively, and engaging for young readers.
    - Encourage imagination and spark a sense of wonder.

**RESPONSE**:
    - **Structure**:
        - Your response *MUST* be the form of a *JSON* blob.
    - **Structure Template**:
```
{synopsis_structure}
```
"""
AT_SYNOPSIS_STRUCTURE = {
    "book_title": "string (maximum 10 tokens / 30 characters, the title of the book)",
    "synopsis": {
        "setting": "string (maximum 100 tokens / 500 characters, describes the setting of the story)",
        "main_character": {
            "name": "string (maximum 10 tokens / 30 characters, name of the main character)",
            "age": "integer (age of the main character)",
            "traits": "string (maximum 50 tokens / 250 characters, description of key personality traits and abilities)",
            "dream": "string (maximum 30 tokens / 150 characters, the main character's goal or aspiration)",
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
