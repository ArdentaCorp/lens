# PRD: AI Image Library and Investigation Assistant

## Summary

Build a system where users upload a library of images, the AI analyzes them, stores metadata, supports search, and answers questions about what appears across the image collection.

## Problem

A large image collection is hard to search, hard to organize, and hard to reason over. Users need a way to ask questions like:

- show me the red car
- find all images with a person
- what seems to be happening across these images
- summarize this set of images

## Goal

Turn a pile of images into searchable evidence and useful conclusions.

## Users

- investigators reviewing image evidence
- operators organizing visual evidence
- teams testing visual search workflows
- developers building AI-based image retrieval workflows

## Core Use Cases

### Image Search

A user searches for a specific object, attribute, or scene and gets matching images.

### Investigation

A user asks a question about a set of images and gets a concise answer based on the matched results.

### Image Collection Analysis

A user selects a batch of images and asks the system to identify patterns, describe what is visible, or form a conclusion.

## Functional Requirements

### Image Library

The system must allow users to:

- upload images
- import a folder of images
- view images in a library
- delete images
- organize images by source or collection

### Image Analysis

The system must:

- analyze each image after upload or import
- detect objects such as person, car, motorcycle, and truck
- extract attributes such as color and scene tags
- store metadata for each image

### Search

The system must support:

- keyword search
- metadata filtering
- search by object type
- search by color
- search by source or collection
- search by timestamp if available

Example queries:

- red car
- person near gate
- white van
- show vehicles from collection A

### Investigation Assistant

The system must:

- retrieve relevant images for a user question
- group or order results meaningfully
- generate a concise grounded summary
- avoid claims not supported by the matched images

## UX Requirements

### Dashboard

Show:

- total images
- recent uploads
- recent analyzed images
- top detected tags or object categories

### Library View

Show:

- image grid
- detected tags
- source or collection
- upload or analysis timestamp

### Search View

Show:

- search input
- filters
- image result grid
- image detail panel

### Investigation View

Show:

- question input
- matched image results
- AI-generated summary

## Technical Stack

### Backend

FastAPI

### Frontend

Streamlit

### Storage

- SQLite for metadata
- local disk for image files

### Processing

- Python workers or background tasks
- object detection pipeline
- metadata extraction pipeline

### AI

- vision model for detection and tagging
- LLM for answering questions over retrieved images

## Data Model

### Image

- id
- filename
- source
- image_path
- created_at
- ingested_at

### ImageAnalysis

- id
- image_id
- detected_objects JSON text
- attributes JSON text
- confidence
- analyzed_at

### InvestigationRecord

- id
- query
- matched_image_ids JSON text
- summary
- created_at

## API

### Images

- `GET /images`
- `POST /images/upload`
- `POST /images/import-folder`
- `GET /images/{id}`
- `DELETE /images/{id}`

### Analysis

- `POST /images/{id}/analyze`
- `POST /images/reindex`

### Search

- `POST /search/images`
- `POST /investigate`

### Health

- `GET /health`

## User Flows

### Upload and Analyze

1. User uploads images
2. Images are stored
3. AI analyzes images
4. Metadata is saved
5. Results appear in the library

### Search

1. User enters a query such as red car
2. System searches metadata
3. Matching images are returned
4. User opens image details

### Investigate

1. User asks a question such as what happened with the red car
2. System retrieves related images
3. AI generates a concise summary

## Success Criteria

- image uploads work reliably
- search returns relevant matches for common object queries
- AI summaries are useful and grounded in matched images
- users can inspect a large image collection without manual image-by-image review
