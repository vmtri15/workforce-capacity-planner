# Workforce learning and cross-training evidence

Reviewed September 15, 2026 from full PDFs supplied by the user through Purdue Library. Page references below are PDF page numbers. Findings describe each study setting; none is observed data from the three modeled facilities. No model parameters were changed.

## Evidence register

### Batt and Gallino (2019): Finding a Needle in a Haystack

DOI: https://doi.org/10.1287/mnsc.2018.3059
Source: `/Users/minhtrivi/Downloads/Finding a Needle in a Haystack.pdf`

- Empirical study of a California online apparel fulfillment center, May 2014–January 2015. Final sample: 2,427,758 pick events and 526 workers (pp. 4–6).
- Mean observed inter-pick time: 49.2 seconds; includes travel between picks and searching. Excludes first picks in shipments, picks above 600 seconds, and other filtered observations. This is not full-shift throughput and must not be directly equated to lines per productive hour.
- Average-effects model estimates 4.2% lower pick time per doubling of cumulative picks (p. 8, Table 4, Model 1). This is not a daily improvement rate or a universal effect. Interaction analysis links learning primarily to searching rather than travel (p. 9).
- Use: strongest reviewed contextual evidence for experience-dependent manual e-commerce picking productivity. Mixed apparel racks and predominantly five-item shipments limit transferability. Routing/assignment gains are simulation results, not achieved project savings.

### Loske (2022): Empirical evidence on human learning and work characteristics in the transition to automated order picking

DOI: https://doi.org/10.1111/jbl.12300
Source: `/Users/minhtrivi/Downloads/EBSCO Full Text Sept 15 2026.pdf`

- Two German grocery warehouses; 100 workers over two months, with 25 incorporation and 25 control workers per system. Approximately 5.76 million picks (pp. 2, 10).
- New-to-system workers already had food-retail logistics experience; they were not complete industry beginners (p. 10).
- Time-based analysis: manual voice-guided, vehicle-supported workers approached experienced performance around 55,000 picks / 5.5–6.5 weeks; automated decision-supported system around 35,000 picks / 3–3.5 weeks (pp. 11–12).
- Multi-input/output efficiency analysis gives approximately 60,000 picks / 6–6.5 weeks for manual and 30,000 / 3–3.5 weeks for automated (p. 14). Efficiency scores are not direct productivity multipliers.
- Grasping/handling/stacking focus excludes travel; these times cannot calibrate full-cycle throughput. Single-company grocery setting limits transferability (pp. 3, 19).
- Use: distinguish initial paid training from continued learning during productive work. Six weeks is a contextual reference, not an established training requirement for this project.

### Giacomelli et al. (2026): An investigation into picking norm times and well-being: fatigue-aware order picking planning

DOI: https://doi.org/10.1080/00207543.2025.2564269
Source: `/Users/minhtrivi/Downloads/Picking Norm Times and Well-Being.pdf`

- Computational experiments with generated demand and literature-based parameters. Initial mean retrieval time of 6.8 seconds describes lifting/lowering, not a full picking cycle (p. 13).
- Heavier-product experiments report 10% lower average modeled fatigue with 1.1% more picking time at the specified target (p. 14). These are scenario results, not universal causal effects.
- Heavy products and motorized picking vehicles; authors explicitly identify walking-based e-commerce picking as requiring further investigation (p. 19).
- Use: support recovery-aware scenario design. Does not validate our 85% productive-time factor, training duration, or picking/packing rates. Supporting data are available from the author upon reasonable request (p. 19).

### Mou (2022): Integrated Order Picking and Multi-Skilled Picker Scheduling in Omni-Channel Retail Stores

DOI: https://doi.org/10.3390/math10091484
Source: `/Users/minhtrivi/Downloads/Integrated Order Picking in Retail.pdf`

- Computational in-store fulfillment model with specialized pickers and flexible associates. Skills are known inputs; numerical experiments vary workforce composition.
- Learning rate 0.95 and experience values are chosen to differentiate proficiency. The author explicitly does not validate a particular learning curve (p. 11). Do not treat 0.95 as post-training productivity.
- Flexible-worker additions can perform similarly to specialist additions under tested conditions; this is not a measured packer-to-picker training effect.
- Training costs, switching time, and allocation across picking/packing/checkout are future research topics (p. 17).
- Use: support considering heterogeneous skills and flexible staffing; not numerical calibration of training hours or productivity penalties.
- Page 11 identifies generated test instances/results in Harvard Dataverse: https://doi.org/10.7910/DVN/HZI7CV . Repository contents have not been inspected; these are not personnel training observations.

### Zhao and Bard (2024): Batch scheduling in a multi-purpose system with machine downtime and a multi-skilled workforce

DOI: https://doi.org/10.1080/00207543.2023.2265508
Source: `/Users/minhtrivi/Downloads/Batch Scheduling Multi-Purpose System.pdf`

- Manufacturing scheduling study using real and generated data based on a Johnson & Johnson operation, with data scaled to protect production capacity (p. 13).
- Existing worker qualifications and availability constrain feasible schedules. A multi-skilled worker can fill only one role in a period; role-by-role headcounts alone may double-count shared workers (pp. 10–13).
- Incorporating the timing and extent of training is proposed as future work (p. 21), not evaluated as a training intervention.
- Use: support eligibility and shared-worker capacity constraints. Does not establish warehouse cross-training productivity or duration. Input/output data are available from authors for academic research (p. 21).

## Decisions and remaining assumptions

1. Keep the reviewed learning evidence separate from cross-training evidence. Learning a familiar workflow over repeated picks does not establish packer-to-picker qualification.
2. A gradual picking learning curve is a proposed scenario extension, not implemented. Any transferred curve requires an explicit reference experience, baseline, bounds, and consistent units.
3. Four paid cross-training hours, 75% cross-role picking productivity, two paid new-hire training days, 80% post-training productivity, and 85% productive time remain assumed sensitivities. The reviewed sources do not calibrate them.
4. Preserve donor packing capacity when redeploying packers and prevent simultaneous assignments. These design choices have supporting scheduling literature.
5. Pause broad learning/cross-training searches. Next priority: measured manual packing productivity with a defined task boundary, order mix, staffing denominator, and equipment setting.

## Next research task: packing

Search `("order fulfillment" OR warehouse) AND (packing OR "packing station") AND ("cycle time" OR productivity OR "time study")`.

Extract whether rates refer to orders, parcels, items, or lines; whether inspection, packaging selection, labeling, sealing, replenishment, and exceptions are included; manual versus automated equipment; sample size and measurement period; and paid versus active working hours. Do not convert parcels/hour into lines/hour without compatible order-mix data. A credible empirical study is sufficient to start; unmatched values remain contextual benchmarks.
