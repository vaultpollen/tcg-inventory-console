# TCG Inventory Management System

## Overview

Problem: Managing trading card inventory through spreadsheets becomes increasingly difficult and time consuming as inventory volume grows. Some specific challenges:

* Inventory location tracking and organization
* Cross-market inventory management
* Order fulfillment efficiency
* Inventory depletion accuracy
* Legacy inventory migration and support

This is a custom warehouse and inventory management system built to manage high-volume trading card inventory across multiple markets and sales platforms at scale.

This lightweight application was developed to replace a spreadsheet-driven workflow with a more scalable and robust inventory database platform capable of handling more demanding inventory ingestion, location management, order fulfillment, depletion tracking, batch storage, and legacy inventory migration.

The system was designed around real operational requirements: Managing thousands of unique SKUs, batch-based storage implemented using chaos storage methodology, efficient pick order flow, inventory depletion logging, and support for merging legacy systems and alternative modern systems run in parallel.

---

## Key Features

### Inventory Ingestion

* Bulk CSV import directly into SQLite database
* Filename-driven metadata extraction
* Automatic batch creation and location assignment
* Import logging and audit trail support
* Manual GUI-supported database updates

Example filename format (the corresponding normalization is based on TCGPlayer and ManaBox export formats):

```text
SI101 MTG Normal en 57 1.csv
```

Parsed automatically into:

* Batch ID
* Card Name
* Game
* Print Type
* Language
* Box
* Segment

### Batch Management

* Creation of location-only batches (for use with other database systems whose inventory is managed separately)
* Batch lookup interface
* Batch movement and reassignment support

### Inventory Search

* Manual card lookup
* Batch lookup
* Legacy inventory fallback

### Fulfillment Workflow

* Pull sheet import
* Optimized pick sheet workflow
* Optimize packing workflow
* Inventory depletion and tracking

### Storage Architecture

* Batch-based chaos storage for physical inventory
* Box and segment location system
* Location resolution abstraction
* Legacy and parallel inventory compatibility layer

---

Core database tables:

* cards_raw
* batches
* box_map
* legacy_locations
* depletion_log
* import_log
* notes

---

## High-Level Technical Concepts

* Database design
* ETL processes
* Inventory and data normalization
* Batch-based physical storage design
* Transaction audit logging
* Data migration from legacy and parallel systems
* Optimized inventory reconciliation
* Fulfillment workflow optimization

### Software Tools

* Python
* Tkinter GUI
* SQLite

## Screenshots

### Main Console

<p align="center">
  <img src="https://github.com/user-attachments/assets/f9bf97e8-dd4e-4160-a49b-cefa6a10a296" width="500">
</p>

<p align="center">
  <em>Main application console.</em>
</p>

---

### Batch Lookup

<p align="center">
  <img src="https://github.com/user-attachments/assets/9e88b033-304f-40db-a5ec-e8870cb65e3a" width="900">
</p>

<p align="center">
  <em>Batch lookup tool for locating inventory batches and resolving storage locations.</em>
</p>

---

### Manual Card Lookup

<p align="center">
  <img src="https://github.com/user-attachments/assets/0558f133-7661-4ebc-883c-d617a42e1314" width="900">
</p>

<p align="center">
  <em>Inventory search interface with quantity visibility, location resolution, and manual depletion.</em>
</p>

---

### Pick Workflow

<p align="center">
  <img src="https://github.com/user-attachments/assets/0808964a-c84f-4e47-a884-9c943deade25" width="1200">
</p>

<p align="center">
  <em>Generated pick workflow used during fulfillment operations.</em>
</p>

---

### Batch Manager

<p align="center">
  <img src="https://github.com/user-attachments/assets/d8b44281-99f0-4b37-9915-40d6d1b87ed0" width="550">
</p>

<p align="center">
  <em>Batch management interface supporting location updates and bulk inventory ingestion.</em>
</p>

---

## Installation

1. Clone repository
2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Create a copy of inventory_template.db and rename the copy to inventory.db. This database is initialized for all of the functionality of the app.

4. Launch application

```bash
python app.py
```
