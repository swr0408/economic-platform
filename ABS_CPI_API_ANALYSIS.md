# ABS CPI API Analysis - SDMX-JSON Format

## API Endpoints

### Data Endpoint
```
https://data.api.abs.gov.au/rest/data/ABS,CPI,/2+3.999903+999902+999901+20001+10001..50.M?dimensionAtObservation=AllDimensions
```

**Headers required:**
```
Accept: application/vnd.sdmx.data+json
```

### Metadata Endpoint
```
https://data.api.abs.gov.au/rest/dataflow/ABS/CPI/?references=all
```

**Headers required:**
```
Accept: application/vnd.sdmx.structure+json
```

---

## 1. Overall JSON Structure

The SDMX-JSON response has this structure:

```json
{
  "meta": {
    "schema": "...",
    "id": "...",
    "prepared": "2026-02-15T09:07:02Z",
    "sender": {...}
  },
  "data": {
    "dataSets": [
      {
        "structure": 0,
        "observations": {
          "0:0:0:0:0:0": [0.3, 0, 0, null, null],
          "0:0:0:0:0:1": [0.3, 0, null, null, null],
          ...
        }
      }
    ],
    "structures": [
      {
        "name": "Consumer Price Index (CPI)",
        "dimensions": {...},
        "attributes": {...}
      }
    ]
  },
  "errors": []
}
```

**Key sections:**
- `meta`: API metadata (schema, timestamp, sender info)
- `data.dataSets[0].observations`: The actual time series data
- `data.structures[0].dimensions`: Dimension definitions and code lists
- `errors`: Error array (empty if successful)

---

## 2. Dimensions and Observation Keys

### Dimension Order (keyPosition)

Observations are stored with keys like `"0:1:2:3:4:5"` where each position represents:

| Position | ID | Name | Description |
|----------|-----|------|-------------|
| 0 | MEASURE | Measure | Type of measurement (MoM, YoY) |
| 1 | INDEX | Index | CPI series (All groups, Trimmed Mean, etc.) |
| 2 | TSEST | Adjustment Type | Seasonal adjustment status |
| 3 | REGION | Region | Geographic area |
| 4 | FREQ | Frequency | Time frequency |
| 5 | TIME_PERIOD | Time Period | Observation date |

**Important:** The numbers in the observation key are **indices** into the dimension value arrays, not the actual codes!

---

## 3. Key Dimension Codes

### INDEX Dimension (Position 1)

The codes you're interested in:

| Code | Name | Parent | Notes |
|------|------|--------|-------|
| **999901** | All groups CPI, seasonally adjusted | 999900 | Primary SA measure |
| **999902** | Trimmed Mean | 999900 | Core inflation measure |
| **999903** | Weighted Median | 999900 | Core inflation measure |
| 10001 | All groups CPI | - | Original (not SA) |
| 20001 | Food and non-alcoholic beverages | 10001 | Category detail |
| 999900 | Underlying trend series | - | Parent category |

### MEASURE Dimension (Position 0)

| Code | Name |
|------|------|
| **2** | Percentage change from previous period (MoM) |
| **3** | Percentage change from previous year (YoY) |

### TSEST Dimension (Position 2) - Adjustment Type

| Code | Name |
|------|------|
| 10 | Original (not seasonally adjusted) |
| 20 | Seasonally Adjusted |

**Note:** For INDEX codes 999901, 999902, 999903, the TSEST value doesn't matter as they are already seasonally adjusted or trend measures.

### REGION Dimension (Position 3)

| Code | Name |
|------|------|
| 50 | Australia |

### FREQ Dimension (Position 4)

| Code | Name |
|------|------|
| M | Monthly |

---

## 4. Time Periods

Time periods are in `YYYY-MM` format. Example from the data:

```json
{
  "id": "2025-12",
  "name": "2025-12",
  "start": "2025-12-01T00:00:00",
  "end": "2025-12-31T00:00:00"
}
```

The current dataset includes:
- **Range:** 2024-05 to 2025-12
- **Frequency:** Monthly

---

## 5. Observation Value Array

Each observation value is an array with this structure:

```json
[0.3, 0, null, null, null]
```

| Position | Attribute | Description |
|----------|-----------|-------------|
| 0 | Value | The actual numeric value |
| 1 | OBS_STATUS | Observation status (0 = revised, null = not revised) |
| 2 | DECIMALS | Decimal places attribute |
| 3 | OBS_COMMENT | Observation comment |
| 4 | Additional | Additional attribute |

**Key point:** You primarily need `value[0]` for the data value.

---

## 6. URL Filter Structure

The URL filter path format:
```
/MEASURE.INDEX.TSEST.REGION.FREQ
```

**Example:**
```
/2+3.999903+999902+999901+20001+10001..50.M
```

Breakdown:
- **MEASURE:** `2+3` = Both MoM (2) and YoY (3)
- **INDEX:** `999903+999902+999901+20001+10001` = Multiple series
- **TSEST:** Empty (all adjustment types)
- **REGION:** `50` = Australia
- **FREQ:** `M` = Monthly

**Note:** Use `+` to request multiple values for a dimension. Use `.` to separate dimensions.

---

## 7. Extracting Time Series Data

### Lookup Table Construction

1. Build dimension value lookups from `structures[0].dimensions.observation`:

```python
def build_dimension_lookup(dimensions, dim_id):
    dim = next(d for d in dimensions if d['id'] == dim_id)
    return {i: val for i, val in enumerate(dim['values'])}

measure_lookup = build_dimension_lookup(dimensions, 'MEASURE')
index_lookup = build_dimension_lookup(dimensions, 'INDEX')
time_lookup = build_dimension_lookup(dimensions, 'TIME_PERIOD')
```

### Parsing Observations

```python
observations = data['data']['dataSets'][0]['observations']

for obs_key, obs_values in observations.items():
    # Parse key: "0:1:2:3:4:5"
    parts = obs_key.split(':')
    measure_idx = int(parts[0])
    index_idx = int(parts[1])
    time_idx = int(parts[5])

    # Get actual codes
    index_code = index_lookup[index_idx]['id']
    measure_code = measure_lookup[measure_idx]['id']
    time_period = time_lookup[time_idx]['id']

    # Get value
    value = obs_values[0]
    is_revised = obs_values[1] == 0

    # Filter for desired series
    if index_code == '999901' and measure_code == '3':  # All groups SA, YoY
        print(f"{time_period}: {value}%")
```

---

## 8. Target Series Identification

### All Groups CPI SA (Seasonally Adjusted)
- **INDEX code:** 999901
- **MEASURE:** 2 (MoM %) or 3 (YoY %)
- **TSEST:** Any (already seasonally adjusted)
- **Example observation key:** `"1:2:0:0:0:10"` → needs lookup

### Trimmed Mean
- **INDEX code:** 999902
- **MEASURE:** 2 (MoM %) or 3 (YoY %)
- **Parent:** 999900 (Underlying trend series)
- **Note:** This is a core inflation measure that excludes volatile items

### Weighted Median
- **INDEX code:** 999903
- **MEASURE:** 2 (MoM %) or 3 (YoY %)
- **Parent:** 999900 (Underlying trend series)
- **Note:** Another core inflation measure

---

## 9. Sample Data Output

### All Groups CPI SA - YoY %
```
2025-07:   3.0%
2025-08:   3.2%
2025-09:   3.6%
2025-10:   3.9%
2025-11:   3.5%
2025-12:   3.7%
```

### Trimmed Mean - YoY %
```
2025-07:   3.0%
2025-08:   3.0%
2025-09:   3.2%
2025-10:   3.3%
2025-11:   3.2%
2025-12:   3.3%
```

### Weighted Median - YoY %
```
2025-07:   3.2%
2025-08:   3.3%
2025-09:   3.5%
2025-10:   3.6%
2025-11:   3.5%
2025-12:   3.6%
```

---

## 10. Implementation Notes

### Key Points:
1. **Observation keys are indices, not codes** - Must build lookup tables first
2. **Value array position 0** contains the actual numeric value
3. **Position 1** indicates revision status (0 = revised)
4. **Time periods** are in YYYY-MM format
5. **Multiple measures** (MoM, YoY) can be in same response
6. **Dimension order** in observation keys must match keyPosition

### Common Pitfalls:
- Don't use observation key numbers directly as dimension codes
- Don't forget to parse the colon-separated observation key
- Remember that INDEX 999901 is already seasonally adjusted (TSEST doesn't matter)
- Date format is YYYY-MM string, not a number

### Performance:
- API responds quickly (~2-3 seconds)
- Returns all requested series in single call
- Efficient to request multiple MEASURE codes (MoM + YoY) at once

---

## 11. Complete Working Example

See `temp_abs_cpi_extraction_example.py` for a complete working implementation that:
- Builds dimension lookup tables
- Extracts specific series by INDEX and MEASURE codes
- Sorts data by date
- Handles revision flags
- Outputs formatted results

**Key function:**
```python
extract_series(data, index_code='999901', measure_code='3')
# Returns: [{'date': '2025-12', 'value': 3.7, 'revised': True}, ...]
```

---

## 12. Additional Resources

- **ABS Methodology:** https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release#methodology
- **SDMX-JSON Schema:** https://github.com/sdmx-twg/sdmx-json
- **Time Series Analysis:** https://www.abs.gov.au/websitedbs/D3310114.nsf/home/Time+Series+Analysis:+The+Basics

---

## Summary

The ABS SDMX-JSON API provides a structured way to access CPI data:
- Use dimension lookups to translate observation key indices to actual codes
- Filter by INDEX codes (999901, 999902, 999903) for the three main CPI measures
- Choose MEASURE code 2 for MoM % or 3 for YoY %
- Extract value from position 0 of the observation value array
- Time periods are in YYYY-MM format and need to be sorted
- A single API call can efficiently retrieve multiple series
