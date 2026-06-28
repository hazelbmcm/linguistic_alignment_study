# Debate Experiment System

## Overview
This is a web-based system developed to host a study on linguistic alignment and misalignment in a debate context. The study aims to investigate the influence of linguistic (mis)alignment on trust and persuasion.

## Demo
To try the experiment system without setup: https://linguistic-alignment-study.onrender.com

## Procedure
Participants complete the following steps
- Pre-experiment survey to capture demographics and background variables
- Six debates with AI agents (three aligned and three misaligned). For each debate:
  - Participants provide an additional agreement rating (1 - 100)
  - Participants provide an initial justification
  - Timed debate (5 minutes)
  - Participants provide a final agreement rating
- Post-experiment survey

## Requirements
- Python 3.11
- Open AI API key

## Installation
- Clone repository and navigate to project folder
- Create and activate a virtual environment
- Install packages:
```
pip install -r requirements.txt
```
Create a `.env` file with the following variables
`OPEN_API_KEY=key`, `EXPORT_KEY=key`, `DB_PATH=experiment.db`

## To Run
Start the server
```
uvicorn main:app --reload
```
Visit
```
http://127.0.0.1:8000
```

