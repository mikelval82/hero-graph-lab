# Architecture Scenarios local API

All operations are scoped to the project currently selected in Graph Lab. A
scenario is immutable after capture.

## List scenarios

`GET /api/scenarios`

Returns scenario summaries without their full snapshots.

## Capture current design

`POST /api/scenarios`

```json
{
  "name": "Alternative A",
  "description": "Optional decision context",
  "snapshot": {
    "nodes": [],
    "edges": [],
    "observed_endpoints": []
  }
}
```

The browser builds this bounded snapshot from the current design overlay. The
server normalizes it again and assigns the immutable id and creation time.

## Retrieve one scenario

`GET /api/scenarios/{scenario_id}`

Returns the complete immutable scenario.

## Compare A with B

`POST /api/scenarios/compare`

```json
{
  "left_id": "scenario-a-id",
  "right_id": "scenario-b-id"
}
```

The response describes changes needed to move from the left scenario to the
right one. Reversing the ids reverses additions and removals. Comparison does not
mutate the active graph and does not select an alternative for implementation.
