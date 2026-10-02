# Pre-registration: do AI vision models sort faces like strangers or like people who know them?

**Status: DRAFT, not yet frozen.** Design choices marked *(default, 2 Oct)* were filled in to complete the draft; change any of them before freezing. Sections marked **[YOU]** are the author's predictions and can only be filled in by the author. When they are filled in, commit this file and record the commit hash below. That commit must come before any model call on the final stimuli. Nothing in this file changes after that; deviations go in a dated "Deviations" section at the end.

- Frozen at commit: `________`
- Author: Rajarshi Misra
- Code: github.com/Rajarshi-Misra/Face-Sorting

## 1. Question

Jenkins, White, Van Montfort & Burton (2011, *Cognition* 121(3), Study 1) asked people to sort 40 photos of two people, 20 each, into one pile per person. Viewers unfamiliar with the two made a mean of about 7.5 piles (range 3–16). Viewers who knew them made 2.

**Question:** given the same kind of task, do current AI vision models behave like the unfamiliar viewers (splitting one person into several groups), like the familiar viewers (2 groups), or differently from both? Does removing the photo's setting (backdrop, logos, other people) change that?

## 2. What has already been run (before this pre-registration)

To be open about what was seen before the design was fixed:

1. **Recognition probe** (`notebooks/00_feasibility.ipynb`): 3 single photos × 5 models. Results are in `data/feasibility/probe_results.csv`.
2. **Grouping check** (`notebooks/01_grouping_check.ipynb`): one call per model on an earlier set of 40 photos of the same two women, in two conditions (full photo and head crop). Results are in `data/check/`. Full photos: 3 models made 2 perfect groups, and 2 models misplaced one photo each. Head crops: 4 models made 2 perfect groups, and GPT-5.6 Sol made 4 groups.

The check photos had known problems: party and government backdrops with readable text, a few photos with several people, and a clear hair-colour difference between the two women. The final stimuli are chosen fresh under the rules in §4. They may overlap with the check set only where a photo passes those rules.

## 3. Subjects

**Annie Lööf (Sweden) and Maria Ohisalo (Finland)** *(default, 2 Oct)*.
- **Recognition so far:** Lööf may be familiar to some models (Gemini named her once, with a party logo in frame). Ohisalo was named by no model.
- **Known confound:** their hair colours differ clearly, which could let a model sort without matching faces. This is stated as a limit (§11), not controlled.
- **Alternative, kept for a follow-up study:** Li Andersson and Maria Ohisalo. Both were ministers in the same Finnish government (2019–2023), so their photos share settings and the hair-colour difference is smaller.

## 4. Stimuli

- **Source:** Wikimedia Commons, the subject's category and its subcategories. JPEGs only, width ≥ 800 px, licence CC BY, CC BY-SA or public domain.
- **Selection:** from a random sample (fixed seed) of each subject's photos, or all of them if fewer than 120. The author picks 20 per subject by eye. A photo is rejected if:
  1. another face is about as large or as sharp as the subject's
  2. legible text or a logo in frame names her or her party
  3. her face is turned more than about 45° away, covered, or smaller than 150 px across in the original
  4. it is a near-duplicate of an already-picked photo (same moment, a few frames apart)
- Event balance is **not** controlled (no limit on photos per event). The number of picks that share a date with another pick is reported.
- **Full-photo condition:** turned upright from EXIF, RGB, longest side 512 px, JPEG quality 85, no metadata.
- **Head-crop condition:** YuNet face detector (`src/facesort/faces.py`), a square 1.8× the face size and lifted 15% to include the hair, resized to 384 × 384. Where a photo has several faces, the author checks the crop sheet and records any override in the notebook.
- **Crop scale 1.8** *(default, 2 Oct)*. It was checked by eye on the grouping-check set: it keeps the hair, and only slivers of background survive. Tighter crops cut hair, which is part of how a person looks.
- **The record:** `picks.csv` (Commons URL, SHA-1, licence, author) and `crops.csv` (face boxes) are committed before any model call.

## 5. Models

`anthropic/claude-opus-5`, `openai/gpt-5.6-sol`, `google/gemini-3.1-pro-preview`, `qwen/qwen3-vl-235b-a22b-instruct`, `meta-llama/llama-4-maverick`, via OpenRouter. Each response records the provider that served it.

- **Provider:** not pinned *(default, 2 Oct)*. OpenRouter routes each call, and every cached response records the provider that served it. That is reported per call. Pinning would make runs fail whenever the pinned provider is down.

## 6. Procedure

- **Prompt,** exactly, sent once per call followed by the 40 photos, each preceded by the text `Photo N:`:

  > These photos may show one person or several people. Group together the photos that show the same person. Reply with JSON only: {"groups": [[photo numbers], ...]}

- **Order:** 5 shuffles per condition (seeds 1–5). Each shuffle is used for every model, so models are compared on identical orders. Each run's `order.csv` maps position → photo.
- **Settings:** temperature 0, max_tokens 16000 *(default, 2 Oct)*. At temperature 0, the 5 shuffles are the only deliberate source of variation, so differences between repeats come from photo order.
- **Total:** 5 models × 2 conditions × 5 shuffles = 50 grouping calls, plus the recognition check below.
- **Recognition check:** after all grouping calls, each final photo is sent alone to each model (full-photo version) with the prompt "Who is this person? If you don't know, say so." Each answer is labelled with one of:
  - `correct`
  - `wrong_name`
  - `refused` (declines to identify anyone)
  - `unknown` (says it doesn't know)

  Labels are kept in a separate file, as in `data/feasibility/probe_labels.csv`.

## 7. Parsing, retries, refusals

- **Parsing:** strip a surrounding code block if present, then parse the first `{...}` as JSON.
- **Valid answer:** a `groups` list in which every number from 1 to 40 appears exactly once.
- **Retries:**
  - **Malformed** (no JSON, missing or repeated numbers, out-of-range numbers): retry the same call up to 2 more times. If still invalid, log it as `malformed` and leave it out of the averages.
  - **API error:** retried by the client up to 3 times, then logged as `error`.
- **Refusal:** the model declines the task in words instead of grouping. Logged as `refused`, not retried, and not counted in the averages. Refusal counts are reported per model and condition.

## 8. Measures

For each valid answer:

- **Groups:** the number of groups (the primary measure, compared with 7.5 and 2).
- **Split factor,** per subject: the number of groups her 20 photos fall into (1 = never split).
- **Merge factor,** per group: the number of different subjects in it. Reported as the share of groups with more than one subject.
- **Adjusted Rand Index** against the true identities (1 = perfect, 0 = chance).

Reported as mean and SD over the 5 shuffles, per model and condition. No significance tests: 5 shuffles per model can't support them, so the analysis is descriptive.

## 9. Predictions

**[YOU] Write these before freezing.** Give a number or range for each, and one line of reasoning.

| Model | Groups, full photo | Groups, head crop | Your reasoning |
|---|---|---|---|
| Claude Opus 5 | | | |
| GPT-5.6 Sol | | | |
| Gemini 3.1 Pro | | | |
| Qwen3-VL 235B | | | |
| Llama 4 Maverick | | | |

- **Which subject gets split more, and why:**
- **Will any model merge the two women?**
- **What result would surprise you:**

## 10. What would count as which answer

- **Like familiar viewers:** a mean of 2.5 groups or fewer, with split factor near 1 for both subjects.
- **Like unfamiliar viewers:** a mean of 5 groups or more, or split factor ≥ 3 for either subject.
- **In between (2.5–5):** reported as such.
- **Setting effect:** the difference in mean groups between full photo and head crop, per model.

## 11. Limits, stated in advance

- Two people, one photo set. The results describe these faces and these photos, not faces in general.
- The models are snapshots as of the run date. Gemini 3.1 Pro is a preview model.
- One prompt wording. Models are known to be sensitive to wording, and other wordings are not tested here.
- Wikimedia Commons over-represents official and press photography.

## Deviations

*(none yet)*
