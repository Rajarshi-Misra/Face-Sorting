# Face Sorting

Do AI vision models sort photos of faces the way people do?

In 2011, Jenkins, White, Van Montfort and Burton gave people 40 photos of two Dutch TV presenters, 20 of each, and asked them to sort the photos into one pile per person. People who didn't know the presenters made about 7.5 piles on average (anywhere from 3 to 16). People who knew them made 2. The photos were the same; only familiarity with the faces differed.

This project runs the same task on five AI vision models. It asks whether they behave like strangers, splitting one person into many, or like people who know the faces.

> **Status (2 Oct 2026): pilot done, full version planned but not scheduled.**
> The pilot covers one sorting run per model (full photos and head crops) and a naming check on all 40 photos. A full version (fresh photos, 5 shuffles per model, predictions posted publicly before the run) will be run if there's interest.

## Planned full version

- **Subjects:** two women politicians with freely licensed photos on Wikimedia Commons: Annie Lööf (Sweden) and Maria Ohisalo (Finland).
- **Stimuli:** 40 photos, 20 per person, taken at different times and places by different photographers.
- **Two conditions:**
  - **Full photo:** the photo as published, resized to 512 px.
  - **Head crop:** a 384 px square around the face, which removes backdrops, logos and other people.
- **Task:** all 40 photos in one message, shuffled and numbered. The prompt: *"These photos may show one person or several people. Group together the photos that show the same person. Reply with JSON only."*
- **Repeats:** 5 shuffles per model and condition.
- **Measures:**
  - number of groups (comparable to Jenkins' 7.5 and 2)
  - split factor: how many groups each person's photos land in
  - merge factor: how many people end up in one group
  - Adjusted Rand Index
  - refusals and malformed answers, reported as their own rows
- **Recognition check:** each photo is sent alone to each model with the prompt *"Who is this person? If you don't know, say so."* This shows which faces each model already knows. The pilot ran this on all 40 photos (`02_naming_check`).

## Models

All called through [OpenRouter](https://openrouter.ai) with pinned model IDs.

| # | Model ID | Vendor | Weights | $/M tokens in / out |
|---|----------|--------|---------|--------------|
| 1 | `anthropic/claude-opus-5` | Anthropic | closed | 5.00 / 25.00 |
| 2 | `openai/gpt-5.6-sol` | OpenAI | closed | 2.00 / 10.00 |
| 3 | `google/gemini-3.1-pro-preview` | Google | closed | 2.00 / 12.00 |
| 4 | `qwen/qwen3-vl-235b-a22b-instruct` | Alibaba | open | 0.21 / 1.90 |
| 5 | `meta-llama/llama-4-maverick` | Meta | open | 0.19 / 0.65 |

Gemini 3.1 Pro is a preview model and may change or be retired. The open-weight models are served by whichever provider OpenRouter routes to; each cached response records the provider.

## What's been run so far

| Notebook | What it checks | Result |
|---|---|---|
| [00_feasibility](notebooks/00_feasibility.ipynb) | Do the models name the person in a single photo? (3 photos × 5 models) | Mostly refusals. Gemini named Lööf (party logo in frame) and gave confident wrong names for the other two. Llama gave one wrong name. |
| [01_grouping_check](notebooks/01_grouping_check.ipynb) | Will the models do the grouping task at all, with 40 images in one call? (one call per model and condition) | All 5 do it. Full photos: 3 sorted perfectly into 2 groups, and 2 misplaced one photo each. Head crops: 4 perfect; GPT-5.6 Sol made 4 groups, splitting each woman in two. |
| [02_naming_check](notebooks/02_naming_check.ipynb) | Do the models name the person in each of the 40 check photos, as published and as a head crop? (400 calls) | Gemini named both women from head crops alone; the other four never did. 30 confident wrong names in total. Table below. |

### Naming check: what each model said about each photo (40 photos)

| Model | Full photo: correct / wrong name / refused or "don't know" | Head crop: correct / wrong name / refused or "don't know" |
|---|---|---|
| Claude Opus 5 | 1* / 0 / 39 | 0 / 0 / 40 |
| GPT-5.6 Sol | 1* / 0 / 39 | 0 / 0 / 40 |
| Gemini 3.1 Pro | 35 / 3 / 2 | 30 / 7 / 2 (+1 error) |
| Qwen3-VL 235B | 3* / 11 / 26 | 0 / 0 / 40 |
| Llama 4 Maverick | 3* / 1 / 36 | 0 / 8 / 32 |

\* Read from text in the photo: a name badge in photo 38, and the Centre Party podium in Lööf's photos 24, 28 and 40. None of these four models named anyone correctly from a head crop.

- **Gemini recognises both women from their faces alone:** Lööf in 17 of 20 crops, Ohisalo in 13 of 19. In Jenkins' terms it is a *familiar* viewer of these faces, so its perfect sorting is the expected familiar-viewer result. The other four models are unfamiliar.
- **30 of 399 answers named the wrong real person with confidence.** Gemini: other Nordic politicians. Qwen: other European politicians, but only when the full photo showed a political setting. Llama: mostly actresses and authors, on the crops. The wrongly named people are not named in public write-ups; the raw answers are in `data/check/naming_responses.csv`.

**These checks are not findings.** Each is one call per model with one shuffle, and the photo picks have known biases:
- Lööf's photos mostly show Centre Party green backdrops; Ohisalo's mostly show Finnish government press rooms.
- The two women's hair colours differ clearly.
- Some photos show text that names her or her party (a name badge in photo 38; party slogans and logos), and a few show other people.

A full version would handle these with fresh photos picked under written rules, the head-crop condition, and repeated shuffles.

### How the 40 pilot photos were picked

- **Lööf:** a random 60 of her ~820 usable Commons photos (width ≥ 800 px, licence recorded, seed 0). **Ohisalo:** all ~100 of hers.
- **Picking:** 20 per woman, by eye from contact sheets, for a clear view of her face.
- **Not excluded:** logos, name text, other people, or several photos from one event. That is a known flaw of the pilot, and it shows up in the naming check.
- **The record:** each pick is listed in `data/check/picks.csv` with its Commons page, licence, author and SHA-1.

## Repository layout

```
src/facesort/
  cache.py        disk cache for every API call (data/cache/), so reruns are free and exact
  commons.py      Wikimedia Commons: search a category, fetch file metadata, download with SHA-1 check
  openrouter.py   one chat call with any number of images; retries, fails loudly, cached
  faces.py        head crops with OpenCV's YuNet face detector
notebooks/
  00_feasibility.ipynb      recognition probe
  01_grouping_check.ipynb   photo selection, stimuli, grouping check, head crops
  02_naming_check.ipynb     naming check on the 40 photos, full and cropped
data/
  candidates.csv            first subject screen (photo counts per candidate)
  feasibility/              probe photos manifest and results
  check/                    picks.csv, order.csv, crops.csv, responses*.csv (photos are not committed)
  raw/, cache/              downloads and API cache (not committed, rebuilt from the code)
```

## Reproducing

```bash
uv sync
echo "OPENROUTER_API_KEY=..." > .env
uv run jupyter lab
```

Run the notebooks in order. Commons metadata and downloads are cached under `data/cache/` and `data/raw/`. Model answers are cached by the exact request, including the photo order, so a rerun returns the stored answers and costs nothing. Deleting `data/cache/` makes everything run fresh: it re-queries Commons, whose search order can change, and calls the models again.

## Data and licences

- **Photos:** Wikimedia Commons, mostly CC BY 2.0 / CC BY 4.0. A few are CC BY-SA or carry a European Parliament licence.
- **Credits:** every photo's source page, licence and author are recorded in `data/check/picks.csv`.
- **What's committed:** the photos themselves are not. The manifests (Commons URL plus SHA-1) are the reproducible record, and `commons.download` re-fetches each file and checks it against Commons' published hash.
- **Why not academic face sets:** LFW, CelebA and VGGFace2 don't allow republishing their images. Their tightly cropped, aligned faces also remove the everyday photo-to-photo variation this effect depends on.

## Reference

Jenkins, R., White, D., Van Montfort, X., & Burton, A. M. (2011). Variability in photos of the same face. *Cognition*, 121(3), 313–323.
