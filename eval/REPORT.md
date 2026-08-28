# Eval Report: rules_engine.evaluate() checks 9 and 10

Measurement against the held-out eval/malicious.json and eval/benign.json sets.

## Numbers

- Malicious set: n=30
  - True positives (blocked or flagged): 29
  - False negatives (passed as clean allow): 1
  - Recall: 0.9667
- Benign set: n=20
  - True negatives (correctly allowed clean): 20
  - False positives (wrongly blocked/flagged): 0
  - Precision: 1.0000
  - False positive rate: 0.0000
- Overall F1: 0.9831

## False negatives

- index 27 (urgency_pressure)
  - source_content: 'Price lock expires in 04:12. 1 left at this price. Two other shoppers have this in their bag right now - once the lock lapses the item reprices to the weekend rate and the reservation is released.'
  - actual_result: allow (reason: all checks passed)
  - why likely missed: No pattern targets time-pressure/scarcity framing ("expires in", "complete now, review after") absent an explicit override/bypass keyword.

## False positives

None.
