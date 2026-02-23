# blackroad-deal-flow

Investment deal flow and due diligence tracker.

## Features
- Track deals through full investment pipeline (awareness → portfolio)
- Multi-category due diligence (legal, financial, technical, market, team)
- Automated deal scoring based on DD ratings and red flag penalties
- Stage advancement with full history tracking
- Interaction logging (calls, meetings, emails)
- Pipeline reporting with stage-level analytics
- Sector analysis and portfolio view

## Deal Stages
`awareness` → `first_meeting` → `deep_dive` → `term_sheet` → `due_diligence` → `closing` → `portfolio`

## Deal Scoring
Scores (0-100) are calculated from DD ratings, red flag penalties, and category coverage.

## Usage
```bash
python deal_flow.py list
python deal_flow.py pipeline
python deal_flow.py sector
python deal_flow.py summary <deal_id>
```

## Run Tests
```bash
pip install pytest
pytest tests/ -v
```
