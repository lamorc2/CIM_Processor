# CIM Processor

Also in this repo: **[yt-pipeline/](yt-pipeline/)** — a local YouTube automation app (Pipecast) with Setup UI, job editor (title/prompts/thumbnails/gameplay), and a script → TTS → FFmpeg → export pipeline. Spec: [`docs/automated-youtube-pipeline-spec.md`](docs/automated-youtube-pipeline-spec.md).

## Project Overview
A Python tool that automates the analysis of Confidential Information Memoranda (CIMs) using a multi-pass LLM pipeline. The processor extracts key financial metrics, qualitative insights, and risk factors from PDF documents, presenting them in a structured, color-coded terminal report.

When the initial text-based extraction returns low or medium confidence, the tool automatically identifies pages likely to contain figures and tables, performs a second-pass visual analysis using image recognition, and merges the results into a final report.

## Motivations
CIMs are dense, lengthy documents — often 50+ pages — that private equity analysts must read and summarize quickly during deal evaluation. The goal of this project was to explore how LLMs could accelerate that process by automating first-pass extraction of the metrics that matter most: revenue, EBITDA, valuation multiples, key risks, and growth opportunities.
This project was also an exercise in building a reliable multi-pass AI pipeline — one that knows when it doesn't have enough information and goes looking for more, rather than returning a confident but incomplete answer.

## Key Features
- **PDF Text Extraction** — Iterates through every page of a CIM using PyMuPDF, feeding content sequentially into the model with full conversation context
- **Structured JSON Output** — Extracts 15+ standardized fields including financials, qualitative factors, and deal metadata
- **Confidence Gating** — Model self-reports confidence (High/Medium/Low); low confidence automatically triggers image analysis, medium prompts the user
- **Two-Pass Image Analysis** — Extracts charts, tables, and figures from flagged pages using PyMuPDF, encodes them as base64, and passes them to the vision model for a second extraction pass
- **CMYK Handling** — Automatically converts CMYK images to RGB before encoding for API compatibility
- **Color-Coded Terminal Report** — Prints a formatted report with ANSI color coding for confidence levels, risk ratings, and missing fields

## About the Author
**Connor LaMora**
- Electrical and Computer Systems Engineering student at Rensselaer Polytechnic Institute
- Passionate about Game Design, Cybersecurity, and all things programming
- For questions or collaboration inquiries, contact me at lamorc2@rpi.edu or connorlamora@gmail.com
