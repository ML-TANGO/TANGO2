# Report Generation Evaluation Docker

This Docker container evaluates radiology report generation by running inference, classification scoring, clinically-weighted relevance (CRG), and natural language generation (NLG) metrics, then merges all results into a single JSON file.

## Metrics

* **NLG** – natural language generation metrics (e.g., BLEU, ROUGE, METEOR).
* **Classification** – multi-label classification metrics on inferred labels (macro F1, AUROC, recall, accuracy, precision).
* **CRG-Score** – clinically-weighted relevance score (see challenge guidelines for weight definitions).

## Input Specification

Mount your predictions JSON to `/input`. The container expects a single `.json` file:

```json
[  
  {
    "input_image_name": "<filename_without_extension>",
    "report": "<generated_report_text>",
    "labels": {
      "abnormality_label_1": <0_or_1>,
      "abnormality_label_2": <0_or_1>,
      ...
    }
  },
  ...
]
```

**Notes:**

* `input_image_name` must match ground-truth identifiers (filenames without `.mha`).
* `report` must be the generated radiology report text.
* `labels` must be binary (0 or 1) for each pathology label.

## Ground-Truth Data

Ground-truth files are baked into the container at:

```
/opt/app/ground-truth/ground_truth.json
/opt/app/ground-truth/ground_truth.csv
```

* `ground_truth.json` is an array of objects with keys:

  * `input_image_name`: string
  * `report`: reference report text
* `ground_truth.csv` is a CSV with columns:

  ```
  input_image_name,abnormality_label_1,abnormality_label_2,...
  ```

  containing binary labels (0 or 1).

## Output Specification

After evaluation, the container writes metrics to `/output/metrics.json`. The JSON has three top-level sections:

1. **`generation`** – NLG metrics object, e.g.:

   ```json
   "generation": {
     "BLEU": <float>,
     "ROUGE_L": <float>,
     "METEOR": <float>,
     ...
   }
   ```

2. **`classification`** – classification metrics object:

   ```json
   "classification": {
     "macro": {
       "f1": <float>,
       "auroc": <float>,
       "recall": <float>,
       "accuracy": <float>,
       "precision": <float>
     }
   }
   ```

3. **`crg`** – clinically-weighted relevance metrics:

   ```json
   "crg": {
     "A": <float>,
     "U": <float>,
     "X": <float>,
     "r": <float>,
     "FN": <int>,
     "FP": <int>,
     "TP": <int>,
     "CRG": <float>,
     "score_s": <float>
   }
   ```

All floats are rounded to four decimal places. The final merged JSON will have exactly these three sections.

## Testing

To verify functionality, run:

```bash
./test.sh
```

Ensure the script is executable:

```bash
chmod +x test.sh
```

## Exporting

Use the `export.sh` script to set environment variables and package the results:

```bash
./export.sh
```

This generates a `.tar.gz` for submission to the challenge platform.

*For questions or issues, please contact the challenge organizers.*
