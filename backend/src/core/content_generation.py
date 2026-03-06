# backend/src/core/content_generation.py

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from config import settings
from typing import Dict, Any
from services.text_generation_provider import build_text_generator
from api.models.book_models import Book
from api.models.helpers import assign_book_model_relationships
from core.prompts import prompts as pt
from core.image_generation import generate_page_illustrations
from core.progress_estimation import GenerationProgressEstimator
from utils.general_utils import generate_presigned_url, get_logger

logger = get_logger(__name__)


async def generate_book(theme: str) -> Book:
    progress = GenerationProgressEstimator(
        logger=logger,
        enabled=settings.enable_generation_progress_estimation,
        log_interval_seconds=settings.generation_progress_log_interval_seconds,
    )
    success = False
    await progress.start()
    try:
        progress.set_stage("generating_story")
        progress.add_total_work(1.0)
        logger.info(f"Generating book with theme: {theme}")
        # Prepare the prompt
        master_prompt = pt.PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS.format(theme=theme)
        output_example = pt.TEMPLATE_CHILDRENS_BOOK
        prompt_content = f"{master_prompt}\n{output_example}"

        # Get the book response
        text_generator = build_text_generator()
        assistant_message = await text_generator.generate_book_response(prompt_content)

        # Parse the assistant's message into a Book object
        try:
            book_data = json.loads(assistant_message)
            book = Book(**book_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing book data: {e}")
            raise

        progress.mark_work_completed(1.0, note="Story content generated.")

        # Assign relationships
        assign_book_model_relationships(book)

        # Set illustration style
        style_attributes = random.choice(pt.ILLUSTRATION_STYLE_ATTRIBUTES)
        book.illustration_style = style_attributes

        # One work unit per page illustration plus one for persisting book JSON.
        progress.set_stage("generating_illustrations")
        progress.add_total_work(float(len(book.pages) + 1))

        # Generate illustrations after creating the book
        illustrations = await generate_illustrations(book, progress)
        expiration_time = timedelta(hours=1)
        expires_at = datetime.now(timezone.utc) + expiration_time

        for page_number, image_data in illustrations.items():
            page = next((p for p in book.pages if p.page_number == page_number), None)
            if page:
                if settings.use_cloud_storage:
                    image_path = f"{book.book_id}/images/{page_number}.png"
                    url = generate_presigned_url(image_path, expiration=3600)
                else:
                    url = str(
                        (
                            Path(settings.local_data_path)
                            / f"{book.book_id}/images/{page_number}.png"
                        ).resolve()
                    )

                # Update illustration with URL and expiration metadata
                page.content.illustration = {
                    "url": url,
                    "expires_at": expires_at,
                }

        success = True
        return book
    except ValueError as e:
        if "content_policy_violation" in str(e):
            raise
        else:
            raise
    finally:
        await progress.stop(success=success)


async def generate_illustrations(
    book: Book, progress: GenerationProgressEstimator
) -> Dict[int, Any]:

    illustrations = await generate_page_illustrations(book, progress)
    return illustrations


if __name__ == "__main__":
    # theme = "An adventure story about a 2 year old girl named June."
    # master_prompt = pt.PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS.format(theme=theme)
    # output_example = pt.TEMPLATE_CHILDRENS_BOOK
    # prompt_content = f"{master_prompt}\n{output_example}"
    # print(prompt_content)
    book_str = """
{
  "book_title": "The Blue Stripe Mystery",
  "book_length_n_pages": 10,
  "characters": [
    {
      "name": "June",
      "description": "A curious and happy toddler who loves to explore.",
      "appearance": "Short curly brown hair, yellow sun hat, red overalls, and white sneakers."
    },
    {
      "name": "Pip",
      "description": "A playful and energetic small puppy.",
      "appearance": "White fur, one black ear, a blue collar, and a wagging tail."
    }
  ],
  "settings": [
    {
      "id": "S1",
      "name": "Sunny Kitchen",
      "visual_anchor_details": "Bright morning light, checkered floor, wooden table, and a green rug."
    },
    {
      "id": "S2",
      "name": "Green Garden",
      "visual_anchor_details": "Soft green grass, pink flowers, a low wooden fence, and blue sky."
    },
    {
      "id": "S3",
      "name": "Cozy Nook",
      "visual_anchor_details": "Warm lamp light, soft striped blanket, a big pillow, and a toy box."
    }
  ],
  "plot_synopsis": "June finds a mysterious blue stripe on the kitchen floor. She follows the trail through the garden with her puppy, Pip. They discover the stripe is actually Pip's long leash. June chooses to follow it all the way back to their cozy nook for a nap.",
  "pages": [
    {
      "page_number": 1,
      "setting_id": "S1",
      "content": {
        "text_content_of_this_page": "June sees a bright blue stripe on the floor. Where does it go?",
        "illustration": "Wide shot. June wears her yellow sun hat and red overalls. She points at a blue ribbon on the checkered kitchen floor. She looks curious.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 2,
      "setting_id": "S1",
      "content": {
        "text_content_of_this_page": "June walks slow. She follows the blue stripe.",
        "illustration": "Medium shot. June crawls on the checkered floor next to the wooden table. She is smiling and focused. The blue line leads toward a door.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 3,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "The stripe goes out to the grass. June goes outside too.",
        "illustration": "Wide shot. June steps onto the soft green grass. The blue stripe winds past pink flowers under the blue sky. June looks excited.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 4,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Look at that! June follows the blue stripe.",
        "illustration": "Medium shot. June is near the low wooden fence. She is bending over to touch the blue stripe in the grass. Her brown curls peek out from her hat.",
        "characters_in_this_page": [
          "June"
        ]
      }
    },
    {
      "page_number": 5,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Pip wags his tail. He has the blue stripe!",
        "illustration": "Medium shot. Pip the puppy stands by the pink flowers. His blue collar is attached to the blue stripe. He looks happy and ready to play.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 6,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Pip runs fast. June runs fast too.",
        "illustration": "Wide shot. Pip runs across the green grass with the blue line trailing behind. June chases him in her white sneakers, laughing loudly.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 7,
      "setting_id": "S2",
      "content": {
        "text_content_of_this_page": "Look at that! June follows the blue stripe.",
        "illustration": "Medium shot. Pip is hiding behind a large flower pot. June is peeking around the corner of the fence with a big grin.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 8,
      "setting_id": "S3",
      "content": {
        "text_content_of_this_page": "The sun goes down. June chooses to go inside.",
        "illustration": "Wide shot. June leads Pip by his blue stripe into the cozy nook. The warm lamp light glows. The toy box is open nearby.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 9,
      "setting_id": "S3",
      "content": {
        "text_content_of_this_page": "Look at that! June follows the blue stripe.",
        "illustration": "Close-up. June and Pip are on the striped blanket. June is taking off her yellow sun hat. They both look very sleepy and calm.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    },
    {
      "page_number": 10,
      "setting_id": "S3",
      "content": {
        "text_content_of_this_page": "June and Pip nap. The blue stripe stays still.",
        "illustration": "Medium shot. June is curled up on a big pillow with Pip. The blue stripe is coiled like a snake on the blanket. Everything is quiet.",
        "characters_in_this_page": [
          "June",
          "Pip"
        ]
      }
    }
  ]
}
"""
    book_data = json.loads(book_str)
    book = Book(**book_data)
    print(book)
