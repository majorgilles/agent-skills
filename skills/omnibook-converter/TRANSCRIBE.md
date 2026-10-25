# Formula transcription (step 6)

Spawn ~7 agents, 3 batches each, with this prompt. Expect ~35% nulls (fragments): they stay exact image crops.

> Transcribe short math-formula images to LaTeX (format conversion of formula snippets only, no prose). Batches:
> batch_NN… in `<repo>/work/crops/` (JSON list of {id, png, text_layer}). For each item: view the PNG with Read;
> write LaTeX for exactly what it shows, no delimiters (\binom{26}{3}, \frac{3\pi}{2}, \sqrt{2}, bmatrix,
> \mathbb{Z}, \mathscr{P}, \emptyset, \lim_{x\to c}). text_layer = the PDF chars in that region (order scrambled,
> radicals/bars missing): every digit/letter must appear. If the image is not a complete self-contained formula
> (sliver, cut-off bracket, piece of a drawing) or you are unsure: null. Never guess. Write
> `<repo>/work/latex/batch_NN.json` {id: latex|null}, valid JSON, confirm it parses. Reply with counts.

`crops.py check` then requires digits, letters and blackboard letters to match the PDF both ways; `apply` swaps
passing ones in as `<span class="tex" data-crop=…>` (the region stays known to the audit).
