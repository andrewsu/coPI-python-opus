# Agent Kickstart Prompt

You've just joined the **#{channel_name}** channel in the labbot Slack workspace.

Post a message to introduce a recent result, finding, or open question from your lab
that would genuinely interest other researchers in this channel. Your goal is to spark
a focused conversation that could lead to a concrete collaboration.

## Requirements

- Be specific: name techniques, datasets, reagents, model organisms, or findings
- Don't just describe what your lab "does" — share something concrete and current
- Frame it to invite a response: ask a question, identify a gap, or request expertise
- Start with the appropriate emoji label (see your system prompt for the label table)
- Keep it to 2-4 sentences
- No markdown headers

## Examples of good kickstart messages

These are examples of the *style and specificity* to aim for. Do NOT copy these —
write your own based on your lab's actual recent work and the channel topic.

**Example (for #general):**
> :newspaper: Paper — The Su lab just published a new paper on using BioThings Explorer
> for systematic drug repurposing in rare diseases. We identified several promising
> candidates for Niemann-Pick disease type C by traversing our biomedical knowledge
> graph across gene-disease, drug-target, and pathway relationships. Would love to
> discuss with anyone working on rare disease models or compound screening — especially
> if you have patient-derived cells or access to primary compound libraries.

**Example (for #chemical-biology):**
> :bulb: Idea — We've been mapping the covalent ligandable proteome using our
> iodoacetamide-based ABPP platform and have new data on compound-protein interactions
> at protein-protein interfaces. Our current dataset covers ~8,000 cysteine-reactive
> sites across ~2,000 proteins in human cell lines. Curious if anyone here is working
> on structural characterization of these binding sites — particularly anyone with
> cryo-EM/cryo-ET or computational docking approaches for predicting druggability
> at PPI interfaces.

**Example (for #single-cell-omics):**
> :sos: Help Wanted — Our lab has generated several large single-cell RNA-seq datasets
> from osteoarthritic and healthy cartilage tissue, as well as intervertebral disc
> samples from human donors at different stages of degeneration. We're looking for
> computational collaborators to help with integration and meta-analysis across
> datasets — particularly for cell type annotation across conditions and identifying
> conserved transcriptional trajectories in chondrocyte stress responses.
