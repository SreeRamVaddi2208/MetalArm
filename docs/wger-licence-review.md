# wger import - licence review

Written by `backend/scripts/import_wger.py library`. Re-run it to refresh.

wger snapshot: **918** exercises with an English name. Imported as new library
exercises: **102**; another **30** library exercises took the image of
their wger twin. Every one ships with its image, its author and licence, and a link
to its wger page; all are listed on `/about/credits`.

Every candidate was then read by hand (`backend/app/data/wger/review.json`):
duplicates of library exercises matched instead of added, non-English or unclear
entries left out, and names, muscles, equipment and category corrected where
wger's were wrong.

## What was allowed

- Images and descriptions under CC-BY-SA 3.0 / 4.0, CC-BY 4.0 or CC0 1.0.
  Attribution: each exercise stores `media_author`, `media_license` and
  `media_source_url`, shown under the artwork and on the credits page.
- Share-alike: the images are adapted (resized, re-encoded) and stay under
  their original licence; the credits page says so. The descriptions are
  reproduced as steps under the same terms, credited through the same link.
- No AI-generated images (wger flags them).

## Imported, by image licence

| Licence | Exercises |
|---|---|
| CC-BY-SA 3.0 | 8 |
| CC-BY-SA 4.0 | 77 |

A further **17** imported exercises keep wger's name and muscles but not its
image or text -
third-party watermarks, logos or copyright notices (which an uploader cannot
licence), or a picture that looks AI-generated though wger does not flag it. They
get MetalArm's own muscle diagram instead.

## Not imported, by reason

| Reason | wger exercises |
|---|---|
| no image | 619 |
| already in the library | 56 |
| already in the library (matched in review) | 44 |
| AI-generated image | 32 |
| no primary muscles | 28 |
| left out in review | 26 |
| duplicate name | 7 |
| name not usable as English | 4 |

Muscles and equipment come through the explicit id maps at the top of the
script; an unmapped id fails the run.
