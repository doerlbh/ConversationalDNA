"""First-person narration and timing for the uncut EACL walkthrough.

Samantha is a clearly disclosed temporary guide voice, not Baihan's voice.
The narration is authored before the actual, continuous window recording.
"""
SEGMENTS = [
(0, 14, 'The problem and atlas',
 "Hi, I'm Baihan. This is Conversational DNA, an interactive atlas of human and AI dialogue. Today I'll explore how contributions fit together when conversations branch and people speak across one another."),
(14, 33, 'Explore and compare',
 "Each point is an indexed episode. I can zoom, select a region, and change what color represents. Here I pin the full collection, then focus on distant responses in Molweni. Participation and annotation coverage change together. That distinction matters when comparing collections."),
(33, 47, 'From population to an exchange',
 "The pathways view counts annotated target and response pairs. I'll select clarification followed by answer, then open a real example. Overlapping windows contribute to these counts; they don't establish whether an exchange succeeded."),
(47, 78, 'Read the visual language',
 "Here is its DNA. Each strand follows one speaker; each base marks a communicative move. Only beads indicate speech. This clarification points back to turn four, across another participant's contribution. The original words stay beside the picture. I can rotate the helix and color bases by move. Twist represents speaker switching, radius represents response distance, and bead size represents word count. Turning these channels off gives a fixed reference for the same exchange."),
(78, 106, 'Inspect and align',
 "The explorer connects the picture to transcripts and source annotations. Lanes and braids offer other views. I can choose an episode, retrieve related interaction patterns, and inspect the exact turn and target correspondences. On held-out annotated motifs, target-aware matching improved precision at five from fifty-eight point eight to seventy-seven point two percent. Visual understanding still needs a user study."),
(106, 120, 'Try and export an interpretation',
 "I can also try an annotation overlay. The source stays intact, and changing the label clears the old comparison. Export preserves the evidence and the overlay, so another reader can examine the interpretation."),
(120, 138, 'Compare observed alternatives',
 "Finally, PRISM records different replies to the same prompt. Here the prompt is: what is love? We can compare the participant's ratings and follow the recorded next round. An unchosen reply has no invented continuation. These are observed alternatives, not causal experiments."),
(138, 149, 'Close with the research question',
 "The methods view explains our sources and limits. My aim is to make conversation's shared structure inspectable, with every interpretation connected to evidence. Thank you.")
]


FULL_SEGMENTS = [SEGMENTS[0],
(14,34,'Explore the collection',
 "The research build contains one point five seven million source records, and maps one hundred and fifty-one thousand indexed episodes. These are eight different collection settings. I can focus on many speakers, clarification moves, or branching targets. Each lens answers a different structural question."),
(34,52,'Inspect what the map measures',
 "Color can show speaker count, response reach, or annotation coverage. I can zoom and pan, then reset the view. The disclosure below the map explains its measured features and principal components. Nearby points have similar descriptors; they need not discuss the same topic."),
(52,68,'Select and export a cohort',
 "I can also select a region directly and export its episode identifiers and comparison settings. The selected cohort remains connected to real conversations. Let me unfold one example, so we can move from a pattern in the collection back to its evidence."),
(68,84,'Search the source text',
 "The explorer also supports text search within a corpus. Here I search Molweni for software. Results retain their source identifiers and annotations. I'll return to the full atlas now, and follow one connected workflow from a population comparison to individual replies.")
] + [(a+70,b+70,title,words) for a,b,title,words in SEGMENTS[1:]]
