# backend/src/core/prompts/prompts.py
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

PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS_V2 = """Write a children's picture book in JSON.

CRITICAL OUTPUT RULES
- Output ONLY valid JSON (no markdown, no code fences, no commentary).
- Use double quotes for all JSON strings.
- Do not include any keys outside the schema below.
- Do not include any dialogue/text inside any "illustration" string.
- Names are case-sensitive and must match EXACTLY across the JSON.

LENGTH / READING LEVEL CONSTRAINTS (enforced via structure)
- Choose "book_length_n_pages" as an integer between 10 and 15.
- The number of entries in "pages" MUST EXACTLY equal "book_length_n_pages".
- Per page text: 1–3 short sentences total, each sentence <= 20 words.
- Vocabulary: simple, concrete words; prefer present tense; avoid abstract concepts.

THEME
{theme}

PLOT REQUIREMENTS
- The story must have a clear toddler-friendly arc:
  - Page 1: hook / curiosity moment
  - Early pages: discovery of a problem or mystery
  - Middle pages: playful attempts and exploration
  - Final pages: satisfying resolution and happy ending
- Include at least 2 setting changes.
- Include at least one clear choice the character(s) make (shown in page text).
- Keep the plot relevant to a child's life/imagination (home, yard, park, toys, animals, imagination play).

CHARACTERS (1 to 5 total)
- Total characters across the entire book: between 1 and 5.
- "characters" is the single source of truth for character names.
- Any name used in any page's "characters_in_this_page" MUST appear ONCE AND ONLY ONCE in "characters".
- "characters_in_this_page" MUST contain ONLY names from "characters" (no nicknames, no roles like "Mom", no new names).
- Each character must have distinct:
  - personality/behavior ("description")
  - physical appearance ("appearance") including 3–5 visual anchors that remain consistent across pages (e.g., hair, outfit, signature item).
- Do not change outfits or major features unless the page text explicitly says so.

SETTINGS (minimal extra structure)
- Add a top-level "settings" array.
- Each setting object must have:
  - "id" (short string like "S1", "S2", etc.)
  - "name" (short label)
  - "visual_anchor_details" (concise but vivid: lighting, key objects, colors, atmosphere)
- Each page MUST include a "setting_id" that matches one of the "settings" ids.
- If the setting does not change from the previous page, reuse the same "setting_id".
- In each page's "illustration", restate the key setting elements so illustrations stay consistent.

ILLUSTRATION GUIDELINES (no text in images)
- Each page "illustration" MUST include:
  - camera framing (close-up / medium / wide)
  - what each character is doing (action/pose)
    - characters should usually be in motion
  - facial expression/mood
  - at least 3 key background elements from the referenced setting
- Absolutely no written words, letters, numbers, signs, captions, or speech bubbles in the illustration description.

BOOK TITLE
- Unique, evocative, curiosity-sparking.
- Avoid generic or overly descriptive titles that summarize the plot.

OUTPUT FORMAT (SCHEMA — do not add/remove keys)
"""

TEMPLATE_CHILDRENS_BOOK_V2 = """{
  "book_title": "The title of the book",
  "book_length_n_pages": 10,
  "characters": [
    {
      "name": "Character Name",
      "description": "Brief description of personality/behavior.",
      "appearance": "Detailed physical description including 3–5 consistent visual anchors."
    }
  ],
  "settings": [
    {
      "id": "S1",
      "name": "Setting name",
      "visual_anchor_details": "Lighting, key objects, colors, atmosphere for visual consistency."
    }
  ],
  "plot_synopsis": "Plot synopsis (<= 60 words).",
  "pages": [
    {
      "page_number": 1,
      "setting_id": "S1",
      "content": {
        "text_content_of_this_page": "1–2 short sentences; each <= 14 words.",
        "illustration": "No text. Include framing, action, expressions, and setting anchors.",
        "characters_in_this_page": ["Character Name"]
      }
    }
  ]
}

Now generate the completed JSON book following all rules above."""

PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS_V3 = """Write a children's book. IMPORTANT!! ENSURE YOUR RESPONSE IS **LESS** THAN 2000 WORDS / 3300 TOTAL_TOKENS.:
 - **Theme**: {theme}
 - **Plot**:
    - Interesting, adventurous, and fun!
    - Relevant in some way to lives or imaginations of the intended audience
- **Book Title**:
  - Should capture the spirit of adventure, theme, and emotion in the story, without being too direct or generic.
  - Aim for a unique, memorable, and evocative title that appeals to children’s imaginations.
  - Avoid overly descriptive titles that summarize the story; instead, think of titles that spark curiosity and wonder about the character’s journey or adventure.
 - **Reading level**: Pre-schoolers.
 - **Characters**:
    - There should be between 1 and 5 characters in the book
    - Characters should have distinct personalities and behaviors
    - Character appearances should be distinct in size, coloring, clothing, facial and body features, and these attributes should distinguish them from one another
    - Any character present in any `page` > `characters_in_this_page` *MUST* also be present *ONCE AND ONLY ONCE* in `characters`
    - Names used in `page` > `characters_in_this_page` must *EXACTLY* match names present in `characters`
 - **Settings**:
    - Add top-level `settings` with at least one, preferably multiple setting changes.
    - Each `settings` entry must include: `id`, `name`, and `visual_anchor_details`.
    - Every page must include `setting_id` that matches one `settings.id`.
    - Reuse `setting_id` when the setting has not changed.
    - In each page `illustration`, describe setting details so generated illustrations remain visually coherent.
 - **`book_length_n_pages`**
    - Length may vary as needed, but should be no less than 10 pages.
    - The parameter of 10 in the example output format below is an example only
    - number of entries in `pages` should *EXACTLY* match `book_length_n_pages`
    - ensure the number of pages *WILL NOT* result in a response greater than 2000 WORDS / 3300 TOTAL_TOKENS
 - **`illustration_values`**:
    - *DO NOT* include any dialogue or text to be depicted in the image. All dialogue should be in the `text_content_of_this_page` value for a given page.
    - Will be used to generate images, so, to keep them coherent, make sure to mention the setting of the image, even if the setting is the same as in the previous page. The setting should be described in detail in `illustration` values.
    - should include the description of characters' action, poses, movements, and/or facial expression where warranted. We don't want illustrations that are boring or overly static.
 - **`characters`>`appearance`**:
    - should be very descriptive
    - These descriptions will be used to generate multiple images, so we need sufficient detail to generate consistent depictions of the characters.
 - **Ensure output is valid JSON (i.e. no syntax errors, opening/closing braces match, escape double quotes in strings, etc.)**
 - **Your response length**: *DO NOT EXCEED 2000 WORDS / 3300 TOTAL_TOKENS* Consider this length limit in determing all parameter values!!

OUTPUT FORMAT:
"""

TEMPLATE_CHILDRENS_BOOK_V3 = """```{"book_title":"The title of the book","book_length_n_pages":10,"characters":[{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."},{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."}],"settings":[{"id":"S1","name":"<Setting name>","visual_anchor_details":"Lighting, key objects, colors, atmosphere for visual consistency."},{"id":"S2","name":"<Setting name>","visual_anchor_details":"Lighting, key objects, colors, atmosphere for visual consistency."}],"plot_synopsis":"Plot synopsis.","pages":[{"page_number":1,"setting_id":"S1","content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}},{"page_number":2,"setting_id":"S1","content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}},{"page_number":3,"setting_id":"S2","content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}}]}```
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

ILLUSTRATION_STYLE_ATTRIBUTES_V2 = [
    "Simple, cartoonish style with thick outlines and bright, primary colors.",
    "Soft watercolor washes with gentle, soothing color transitions.",
    "Vibrant and textured illustrations with bold, expressive brushstrokes.",
    "Playful, hand-drawn doodles with a sketchy, dynamic feel.",
    "Flat design with minimal shading, focusing on bold, geometric shapes.",
    "Realistic, detailed animals in lush, nature-inspired scenes.",
    "Whimsical, abstract style using unusual shapes and exaggerated features.",
    "Chalk pastel textures with a warm, fuzzy feeling and muted tones.",
    "Vintage-inspired, muted color palette with textured backgrounds.",
    "3D-rendered characters with smooth, rounded forms and soft lighting.",
    "Collage-style using cut-out paper textures, layering shapes and colors.",
    "Digital illustrations with high contrast and glossy, polished finishes.",
    "Pastel crayons and pencil strokes creating a soft, nostalgic atmosphere.",
    "Stylized, elongated characters with exaggerated proportions and movement.",
    "Bold, comic book style with action-packed scenes.",
    "Delicate, intricate line work with floral patterns and elegant details.",
    "Neon accents and high-energy designs with a futuristic, dynamic flair.",
    "Mixed media, combining photography and drawing for a surreal effect.",
    "Black and white illustrations with intricate cross-hatching and shading.",
    "Textured acrylic paint strokes, giving a rough, tactile feel to the pages.",
    "Impressionistic brushstrokes creating dreamlike, flowing scenes.",
    "Blocky, pixel art-inspired style with a retro video game aesthetic.",
    "Bold, minimalistic shapes with a striking, limited color palette.",
    "Organic, fluid lines that evoke a sense of movement and nature.",
    "High-contrast silhouettes with dramatic lighting and shadow play.",
    "Vintage comic strip style with sepia tones and retro text bubbles.",
    "Stylized, angular shapes with sharp lines and a modern, edgy vibe.",
    "Soft, plushy textures that evoke the feel of stuffed toys or fabric.",
    "Hand-painted textures with visible brushstrokes and a lively color palette.",
    "Rustic, folk art style with earthy tones and handcrafted details.",
    "Pastel, dreamy clouds and soft character designs in a fantasy world.",
    "Dynamic, action-focused poses with bright, energetic backgrounds.",
    "Stained glass-inspired designs with sharp divisions and vibrant colors.",
    "Delicate watercolor landscapes with minimal characters for a calm feel.",
    "Whimsical, exaggerated characters with big eyes and quirky expressions.",
    "Detailed, storybook fantasy art with intricate castles and magical creatures.",
    "High-detail line drawings filled with intricate patterns and hidden details.",
    "Playful, scribbly lines mimicking a child’s own drawings.",
    "Hand-cut, paper puppet style with layers and textural elements.",
    "17th-century Flemish masterpiece painting style",
]

PROMPT_PAGE_ILLUSTRATION_PREFACE = """Create an illustration for children's book according to the following specification (follow the specification *EXACTLY*):"""
PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE = (
    "Extract and use the illustration style of the attached image. "
    "You are *NOT* editing the attached image. "
    "You are generating a new image as described in `illustration_description` "
    "and `text_content`."
)
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
