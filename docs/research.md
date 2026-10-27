# Research Methodology

## Guidelines
- Follow scientific language guidelines for all documentation.
- Maintain a reproducibility checklist for every published model.

## Limitations
- AI models are statistical and can make errors.
- External factors (shell thickness, diet) may confound visual features.
- System cannot legally claim to guarantee food safety.

## Freshness-model release gate

No model may be enabled in the product just because it produces a class label. Before a model version is marked ready, retain a signed validation record containing:

- a versioned dataset with egg IDs, capture conditions, and linked intact-image/ground-truth records;
- group-separated train, validation, and held-out test partitions so images of one egg never cross partitions, plus a farm-held-out test where possible;
- the target definition and laboratory measurement protocol (for example, Haugh Unit), sample coverage by shell type, farm, camera, lighting, storage temperature, and age;
- classification and regression metrics with confidence intervals, calibration/error analysis, and subgroup results—not a single headline accuracy;
- acceptance limits approved by the responsible domain expert, along with explicit conditions where the model must abstain;
- inference reproducibility data: code commit, dataset version, preprocessing version, random seed, model artifact hash, runtime, and model-card limitations.

After deployment, track abstention rate, image-quality failures, confidence/calibration drift, and performance on reviewed ground-truth samples. Retrain or disable the model when acceptance limits are violated. This gate is the closest defensible path to trustworthy performance; it cannot make a biological prediction 100% guaranteed.

## Future Directions
- Multi-spectral imaging
- Acoustic resonance testing fusion
